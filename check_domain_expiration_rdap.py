#!/usr/bin/env python

import argparse
import datetime
import logging
import requests

import nagiosplugin
import pandas
import pyunycode
import requests_cache

_log = logging.getLogger('nagiosplugin')

list2dict = []

session = requests_cache.CachedSession(
    '/tmp/iana_rdap_cache', 
    cache_control=True
)
req = session.get('https://data.iana.org/rdap/dns.json')
for list_of_list in req.json()['services']:
    k,v = list_of_list
    for x in k:
        list2dict.append({'name':x, 'url':v[0]})

df = pandas.DataFrame(list2dict)

def expiration(domain):
    domain = pyunycode.convert(domain)
    tld = domain.split('.')[-1]
    try:
        url = df[df.name == (tld)].iloc[0].url
    # no rdap on tld
    except IndexError:
        raise nagiosplugin.CheckError(
            f'The TLD {tld} does not have an RDAP server'
        )

    req_rdap = requests.get(f'{url}domain/{domain}')

    raw_expiration = [
        event.get('eventDate', False)
        for event in req_rdap.json().get('events', {})
        if event.get('eventAction', {}) == 'expiration'
    ]

    try:
        fecha = raw_expiration[0].split('T')[0]
    except IndexError:
        raise nagiosplugin.CheckError(
            f'The domain {domain} has not been found'
        )

    today = datetime.datetime.now()
    delta = datetime.datetime.strptime(fecha, '%Y-%m-%d') - today
    return(delta.days)


# data acquisition

class Expiration(nagiosplugin.Resource):
    """Domain model: domain expiration

    Get the expiration date from RDAP.
    The RDAP server is extracted from https://data.iana.org/rdap/dns.json which
    cached to avoid useless fetching; but the JSON from the registry RDAP isn’t
    cached because we can’t presume of the data lifetime.
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
    argp.add_argument('domain')
    args = argp.parse_args()
    wrange = f'@{args.critical}:{args.warning}'
    crange = f'@~:{args.critical}'
    fmetric = '{value} days until domain expires'

    check = nagiosplugin.Check(
        Expiration(args.domain),
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
