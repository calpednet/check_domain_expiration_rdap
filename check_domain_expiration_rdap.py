#!/usr/bin/env python

# Copyright 2024 Alarig Le Lay <alarig@swordarmor.fr>
# Distributed under the terms of the GNU General Public License v3

import argparse
import datetime
import logging
import requests

import nagiosplugin
import requests_cache

_log = logging.getLogger('nagiosplugin')

# cache session for json and csv storage
session = requests_cache.CachedSession(
    '/tmp/iana_rdap_cache',
    cache_control=True
)

def find_rdap_server(domain):
    """Find the TLD rdap server."""
    import pandas

    list2dict = []
    req = session.get('https://data.iana.org/rdap/dns.json', timeout=120)
    for k,v in req.json()['services']:
        for x in k:
            list2dict.append({'name':x, 'url':v[0]})

    df = pandas.DataFrame(list2dict)

    tld = domain.split('.')[-1]
    try:
        url = df[df.name == (tld)].iloc[0].url
    # no rdap on tld
    except IndexError:
        raise nagiosplugin.CheckError(
            f'The TLD {tld} does not have an RDAP server'
        )

    _log.debug(f'The used RDAP server is {url}')

    return url


def parse_ldap(domain, rdap_server):
    req_rdap = requests.get(f'{rdap_server}domain/{domain}')

    match req_rdap.status_code:
        case 403:
            raise nagiosplugin.CheckError(
                f'Got {req_rdap.status_code}, the RDAP server {rdap_server} refused to reply'
            )
        case 404:
            raise nagiosplugin.CheckError(
                f'Got {req_rdap.status_code}, the domain {domain} has not been found'
            )
        case 409:
            raise nagiosplugin.CheckError(
                f'Got {req_rdap.status_code}, the RDAP server {rdap_server} has too many requests'
            )
        case 503:
            raise nagiosplugin.CheckError(
                f'Got {req_rdap.status_code}, the RDAP server {rdap_server} seems broken'
            )
        case _:
            pass

    _log.debug(f'The used RDAP JSON from {req_rdap.url} is {req_rdap.json()}')

    raw_expiration = [
        event.get('eventDate', False)
        for event in req_rdap.json().get('events', {})
        if event.get('eventAction', {}) == 'expiration'
    ]

    # if we have not found the field expiration in the list eventAction
    if len(raw_expiration) == 0:
        _log.debug(f'The domain JSON for {domain} does not have "eventAction"."expiration" field, run with -vvv or --debug to have the JSON dump')
        raw_registrar = [
            entity.get('vcardArray', False)
            for entity in req_rdap.json().get('entities', {})
            if 'registrar' in entity.get('roles')
        ]

        # I hope that order of the fields is consistent
        # and I do not know at all what fn means
        # We try to find the registrar here
        for line in raw_registrar[0][1]:
            if 'fn' in line:
                raw_expiration.append(line[3])

    elif len(raw_expiration) == 1:
        fecha = raw_expiration[0].split('T')[0]
        today = datetime.datetime.now()
        delta = datetime.datetime.strptime(fecha, '%Y-%m-%d') - today
        raw_expiration[0] = delta.days

    else:
        raise nagiosplugin.CheckError(
            f'{raw_expiration} is too long'
        )

    return raw_expiration

def expiration(domain):
    """Find the expiration date for the domain."""

    raw_expiration = parse_ldap(domain, find_rdap_server(domain))

    # we have parsed the eventAction field about expiration
    if isinstance(raw_expiration[0], int):
        return raw_expiration[0]
    # we have not, so we try to fall back to registrar ldap
    elif isinstance(raw_expiration[0], str):
        import csv
        # fetch csv
        iana_registrars_csv = session.get(
            'https://www.iana.org/assignments/registrar-ids/registrar-ids-1.csv',
            timeout=120
        ).content.decode('utf-8')
        # parse csv
        registrar_rdap_found = False
        for registrar_row in csv.reader(
            iana_registrars_csv.splitlines(),
            delimiter=','
        ):
            # lower case comparaison just in case (haha)
            if registrar_row[1].lower() == raw_expiration[0].lower():
                # re-query
                _log.debug(f'Falling back to registrar RDAP: {registrar_row[3]}')
                registrar_rdap_found = True
                registrar_expiration = parse_ldap(domain, registrar_row[3])
                if isinstance(registrar_expiration[0], int):
                    return registrar_expiration[0]
                else:
                    raise nagiosplugin.CheckError(
                        f'Neither TLD or {registrar_row[3]} have expiration data'
                    )
        if not(registrar_rdap_found):
            raise nagiosplugin.CheckError(
                f'The registrar {raw_expiration[0]} is not fond from {iana_registrars_csv.url}'
            )

    else:
        raise nagiosplugin.CheckError(
            f'Error while parsing the JSON, {raw_expiration[0]} does not have an expected format'
        )


# data acquisition

class Expiration(nagiosplugin.Resource):
    """Domain model: domain expiration

    Get the expiration date from RDAP.
    The RDAP server is extracted from https://data.iana.org/rdap/dns.json which
    cached to avoid useless fetching; but the JSON from the registry RDAP is
    not cached because we can not presume of the data lifetime.
    """

    def __init__(self, domain):
        self.domain = domain

    def probe(self):
        try:
            days_to_expiration = expiration(self.domain)
        except requests.exceptions.ConnectionError as err:
            raise nagiosplugin.CheckError(
                f'The connection to the RDAP server failed: {err}'
            )

        return [nagiosplugin.Metric(
            'daystoexpiration',
            days_to_expiration,
            uom='d'
        )]


# data presentation

class ExpirationSummary(nagiosplugin.Summary):
    """Status line conveying expiration information.
    """

    def __init__(self, domain):
        self.domain = domain

    pass


# runtime environment and data evaluation

@nagiosplugin.guarded
def main():
    import pyunycode

    argp = argparse.ArgumentParser(description=__doc__)
    argp.add_argument(
        '-w', '--warning', metavar='int', default='30', 
        help='warning expiration max days. Default=30'
    )
    argp.add_argument(
        '-c', '--critical', metavar='range', default='15',
        help='critical expiration max days. Default=15'
    )
    argp.add_argument(
        '-v', '--verbose', action='count', default=0, help='be more verbose'
    )
    argp.add_argument(
        '-d', '--debug', action='count', default=0,
        help='debug logging to /tmp/nagios-check_domain_expiration_rdap.log'
    )
    argp.add_argument('domain')
    args = argp.parse_args()
    wrange = f'@{args.critical}:{args.warning}'
    crange = f'@~:{args.critical}'
    fmetric = '{value} days until domain expires'

    if (args.debug):
        logging.basicConfig(
            filename='/tmp/nagios-check_domain_expiration_rdap.log',
            encoding='utf-8',
            format='%(asctime)s %(message)s',
            level=logging.DEBUG
        )

    domain = pyunycode.convert(args.domain)
    check = nagiosplugin.Check(
        Expiration(domain),
        nagiosplugin.ScalarContext(
            'daystoexpiration',
            warning=wrange,
            critical=crange,
            fmt_metric=fmetric
        ),
        ExpirationSummary(args.domain)
    )
    check.main(verbose=args.verbose)


if __name__ == '__main__':
    main()
