Script intented to check a domain expiration with a query to the corresponding
RDAP server.

This script is inspired from
https://raw.githubusercontent.com/buanzo/check_expiration_rdap/main/src/nagios_check_domain_expiration_rdap/nagios_check_domain_expiration_rdap.py
and `/usr/lib/python3.11/site-packages/nagiosplugin/examples/`

The script assumes that the TLD has only one label while looking for the RDAP
server from the IANA JSON. If it’s not the case it will fail.

I don’t understand half of what I wrote

Have fun.

Here are the tested cases:
```shell
# expired domain
alarig@x280 nagios-check_domain_expiration_rdap % (master *+%) ./check_domain_expiration_rdap.py found.com.br
EXPIRATION CRITICAL - -31 days until domain expires (outside range @~:15) | daystoexpiration=-31d;@15:30;@~:15
zsh: exit 2     ./check_domain_expiration_rdap.py found.com.br

# not reachable rdap server
alarig@x280 nagios-check_domain_expiration_rdap % (master *+%) ./check_domain_expiration_rdap.py 美しい.世界
EXPIRATION UNKNOWN - The connection to the RDAP server failed: HTTPSConnectionPool(host='rdap.teleinfo.cn', port=443): Max retries exceeded with url: /xn--rhqv96g/domain/xn--n8jub8754b.xn--rhqv96g (Caused by NewConnectionError('<urllib3.connection.HTTPSConnection object at 0x7f92a5d24650>: Failed to establish a new connection: [Errno 111] Connection refused'))
zsh: exit 3     ./check_domain_expiration_rdap.py 美しい.世界

# unexistant domain name
alarig@x280 nagios-check_domain_expiration_rdap % (master *+%) ./check_domain_expiration_rdap.py foundnotfound.fr
EXPIRATION UNKNOWN - The domain foundnotfound.fr has not been found
zsh: exit 3     ./check_domain_expiration_rdap.py foundnotfound.fr

# tld without rdap server
alarig@x280 nagios-check_domain_expiration_rdap % (master *+%) ./check_domain_expiration_rdap.py c.pt
EXPIRATION UNKNOWN - The TLD pt does not have an RDAP server
zsh: exit 3     ./check_domain_expiration_rdap.py c.pt

# domain with more than two labels
alarig@x280 nagios-check_domain_expiration_rdap % (master *+%) ./check_domain_expiration_rdap.py demarches.gouv.fr
EXPIRATION OK - 113 days until domain expires | daystoexpiration=113d;@15:30;@~:15

# unicode domain
alarig@x280 nagios-check_domain_expiration_rdap % (master *+%) ./check_domain_expiration_rdap.py こっち.みんな
EXPIRATION OK - 268 days until domain expires | daystoexpiration=268d;@15:30;@~:15

# near expiration domain
alarig@x280 nagios-check_domain_expiration_rdap % (master *+%) ./check_domain_expiration_rdap.py hostux.ninja
EXPIRATION WARNING - 17 days until domain expires (outside range @15:30) | daystoexpiration=17d;@15:30;@~:15
zsh: exit 1     ./check_domain_expiration_rdap.py hostux.ninja

# very far expiration domain
alarig@x280 nagios-check_domain_expiration_rdap % (master *+%) ./check_domain_expiration_rdap.py swordarmor.fr
EXPIRATION OK - 3615 days until domain expires | daystoexpiration=3615d;@15:30;@~:15
```
