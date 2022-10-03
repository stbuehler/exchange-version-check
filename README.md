# exchange-version-check

The check_stbuehler_exchange_version script has to modes:

- `check` (default)
- `pages`

## check

Icinga/nagios compatible plugin to check exchange server version.

Currently looks for the `X-OWA-Version` header in the response for `http[s]://server/AutoDiscover/AutoDiscover.xml`.

## pages

Create machine (and human) readable list of exchange versions with an heuristic flag whether they are good to use.

Heuristic is as follows:

- must be less than 180 days old
- must be less than 31 days older than a release on a neighbor branch

Versions are parsed from https://docs.microsoft.com/en-us/exchange/new-features/build-numbers-and-release-dates (sadly Microsoft killed the https://github.com/MicrosoftDocs/OfficeDocs-Exchange repository with the markdown source).
