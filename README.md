# exchange-version-check

Create machine (and human) readable list of exchange versions with an heuristic flag whether they are good to use.

Heuristic is as follows:

- must be less than 180 days old
- must be less than 31 days older than a release on a neighbor branch

Versions are parsed from https://github.com/MicrosoftDocs/OfficeDocs-Exchange/blob/public/Exchange/ExchangeServer/new-features/build-numbers-and-release-dates.md

Goal: create an icinga/nagios check to run against exchange servers to check their version.
