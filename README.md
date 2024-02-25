# exchange-version-check

The check_stbuehler_exchange_version script has to modes:

- `check` (default)
- `pages`

## check

Icinga/nagios compatible plugin to check exchange server version.

Currently looks for the `X-OWA-Version` header in the response for `http[s]://server/AutoDiscover/AutoDiscover.xml`.

## pages

Create machine (and human) readable list of exchange versions with an heuristic flag whether they are good to use.

Versions are parsed from <https://docs.microsoft.com/en-us/exchange/new-features/build-numbers-and-release-dates>.

Supported CU versions are parsed from <https://learn.microsoft.com/en-us/exchange/plan-and-deploy/supportability-matrix>.
