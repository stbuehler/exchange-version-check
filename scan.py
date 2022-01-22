#!/usr/bin/env python3

import dataclasses
import datetime
import json
import re
import typing
import yaml
import requests


_MATCH_MD_LINK = re.compile(r'\[(.+?)\]\((.+?)\)')
# support simple links
def from_markdown(md: str) -> typing.Tuple[str, typing.Optional[str]]:
	plain = ''
	html = ''
	while True:
		m = _MATCH_MD_LINK.search(md)
		if not m:
			plain += md
			html += md
			break
		pre = md[:m.start(0)]
		plain += pre
		html += pre
		md = md[m.end(0):]
		#
		plain += m[1]
		html += f'<a href="{m[2]}">{m[1]}</a>'
	if plain == html:
		return (plain, None)
	return (plain, html)


@dataclasses.dataclass
class Version:
	name: str
	short_code: str
	date: typing.Optional[datetime.date]
	date_str: typing.Optional[str]
	html_name: typing.Optional[str]

	_SPLIT_TITLE = re.compile(r'^\[(.+)\]\((.+)\)$')
	_FIX_DATE_WS = re.compile(r'([a-zA-Z])([0-9])')

	@property
	def date_string(self) -> str:
		if not self.date_str is None:
			return self.date_str
		assert self.date
		return self.date.strftime('%Y-%m-%d')

	@property
	def num_code(self) -> typing.Sequence[int]:
		return tuple(int(p) for p in self.short_code.split('.'))

	@staticmethod
	def _parse_date(col: str) -> typing.Tuple[typing.Optional[str], typing.Optional[datetime.date]]:
		# May25 -> May 25
		col = Version._FIX_DATE_WS.sub(r'\1 \2', col.strip())
		try:
			# Month day, Year
			date = datetime.datetime.strptime(col, '%B %d, %Y')
			return (None, date.date())
		except ValueError: pass
		try:
			# Month, Year
			date = datetime.datetime.strptime(col, '%B, %Y')
			return (date.strftime('%Y-%m'), date.date())
		except ValueError: pass
		try:
			# Month Year
			date = datetime.datetime.strptime(col, '%B %Y')
			return (date.strftime('%Y-%m'), date.date())
		except ValueError: pass
		return (f'Unknown: {col}', None)

	@staticmethod
	def parse_line(line: str):
		cols = line.removeprefix('|').removesuffix('|').split('|')
		name = cols[0].strip()
		while name.startswith('&nbsp;'):
			name = name.removeprefix('&nbsp;').lstrip()
		html_name: typing.Optional[str] = None
		name, html_name = from_markdown(name)
		date_str, date = Version._parse_date(cols[1])
		short_code = cols[2]
		return Version(
			name=name,
			short_code=short_code,
			date=date,
			date_str=date_str,
			html_name=html_name,
		)

	@staticmethod
	def scan(input: str):
		for line in input.splitlines():
			if not line.startswith('|'):
				continue
			if line.startswith(('|Product name|', '|---|', '||')) or line == '|':
				continue
			yield Version.parse_line(line)

	def to_yaml(dumper: yaml.Dumper, data: 'Version'):
		state = {
			key: value
			for key, value in data.__dict__.items()
			if value
		}
		if data.date_str:
			# if we have date_str then date is not an exact representation
			state.pop('date', None)
		return dumper.represent_mapping('tag:yaml.org,2002:map', state.items())
yaml.Dumper.add_representer(Version, Version.to_yaml)


@dataclasses.dataclass
class Tree(yaml.YAMLObject):
	path: typing.Sequence[int]
	name: str
	html_name: typing.Optional[str]
	version: typing.Optional[Version]
	children: typing.List['Tree']
	latest_release: typing.Optional[datetime.date] = None
	latest_release_str: typing.Optional[str] = None
	alive: typing.Optional[bool] = None

	_TOTAL_MAX_AGE = datetime.timedelta(days=180)
	_COMPARE_MAX_AGE = datetime.timedelta(days=31)

	@property
	def short_code_wild(self) -> str:
		if not self.path: return '*'
		return '.'.join(map(str, self.path)) + '.*'

	@property
	def latest_release_string(self) -> typing.Optional[str]:
		if not self.latest_release_str is None:
			return self.latest_release_str
		if self.latest_release:
			return self.latest_release.strftime('%Y-%m-%d')
		return None

	def _is_flat_version(self):
		return self.version and 0 == len(self.children)

	def _calc_alive(self, parent_alive: bool=True, parent_latest_release: typing.Optional[datetime.date]=None):
		alive = bool(
			parent_alive and
			self.latest_release and
			(datetime.date.today() - self.latest_release) < Tree._TOTAL_MAX_AGE
		)
		if self.version and alive:
			assert self.latest_release
			if parent_latest_release and (parent_latest_release - self.latest_release) > Tree._COMPARE_MAX_AGE:
				alive = False
		self.alive = alive
		for node in self.children:
			node._calc_alive(alive, self.latest_release)

	def _fix_tree(self):
		guess_name = True
		calc_release_date = True
		release_dates: typing.List[typing.Tuple[datetime.date, typing.Optional[str]]] = []
		if self.version and self.version.date:
			release_dates.append((self.version.date, self.version.date_str))
		for node in self.children:
			node._fix_tree()
			if calc_release_date:
				if node.latest_release:
					release_dates.append((node.latest_release, node.latest_release_str))
				else:
					calc_release_date = False
			if not node._is_flat_version():
				guess_name = False
		if guess_name and (not self.name) and (not self.version) and len(self.children):
			self.name = self.children[-1].version.name
			self.html_name = self.children[-1].version.html_name
		if calc_release_date and len(release_dates):
			d, d_str = max(release_dates)
			self.latest_release = d.replace()  # clone date
			self.latest_release_str = d_str

	def html_table(self, out, *, nested: int=0):
		if self.alive:
			dead_color_cls = ''
		else:
			dead_color_cls = ' class="text-danger"'
		if self.alive and self.version:
			dead_collapse_cls = ''
		else:
			dead_collapse_cls = ' class="collapse show vt-collapse-dead"'
		indent = f'style="padding-left: {2*nested}em;"'
		skip = False
		if self.version:
			name = self.version.html_name or self.version.name
			code = self.version.short_code
			date: typing.Optional[str] = self.version.date_string
		elif self.name:
			name = self.html_name or self.name
			code = self.short_code_wild
			date = self.latest_release_string
		else:
			skip = True
		if not skip:
			out.write(f'<tr{dead_collapse_cls}><td {indent}>{name}</td><td{dead_color_cls}>{code}</td><td{dead_color_cls}>{date}</td></tr>\n')
		for node in self.children:
			node.html_table(nested=nested+1, out=out)

	def gather_alive_versions(self) -> typing.Iterator[Version]:
		if self.alive and self.version:
			yield self.version
		for node in self.children:
			for v in node.gather_alive_versions():
				yield v

	def to_yaml(dumper: yaml.Dumper, data: 'Tree'):
		state = {
			key: value
			for key, value in data.__dict__.items()
			if value and not key in ('path',)
		}
		if data.latest_release_str:
			# if we have a string the date isn't exact
			state.pop('latest_release', None)
		return dumper.represent_mapping('tag:yaml.org,2002:map', state.items())
yaml.Dumper.add_representer(Tree, Tree.to_yaml)


@dataclasses.dataclass
class TreeBuilder(yaml.YAMLObject):
	path: typing.Sequence[int]
	name: str = ''
	html_name: typing.Optional[str] = ''
	version: typing.Optional[Version] = None
	children: typing.Dict[int, 'TreeBuilder'] = dataclasses.field(default_factory=dict)

	def _subnode(self, key: int) -> 'TreeBuilder':
		node = self.children.get(key, None)
		if node is None:
			node = TreeBuilder(path=tuple(self.path) + (key,))
			self.children[key] = node
		return node

	def _insert_name(self, path: typing.Sequence[int], name: str):
		if len(path) == 0:
			self.name = name
			return
		key = path[0]
		path = path[1:]
		self._subnode(key)._insert_name(path, name)

	def _insert(self, path: typing.Sequence[int], version: Version):
		if len(path) == 0:
			assert self.version is None, f'Version already in tree: {version} ({self.version})'
			self.version = version
			return
		key = path[0]
		path = path[1:]
		self._subnode(key)._insert(path, version)

	def _gather_top_trees(self):
		if self.name or self.version:
			t = self._flatten_tree()
			t._fix_tree()
			t._calc_alive()
			yield t
		else:
			for key, node in sorted(self.children.items(), reverse=True):
				for tt in node._gather_top_trees():
					yield tt

	def _flatten_tree(self) -> Tree:
		children = [
			node._flatten_tree()
			for _key, node in sorted(self.children.items(), reverse=True)
		]
		if not self.name and not self.version and len(children) == 1:
			return children[0]
		return Tree(
			path=self.path,
			name=self.name,
			html_name=self.html_name,
			version=self.version,
			children=children,
		)

	@staticmethod
	def from_versions(versions: typing.Iterable[Version]) -> typing.List['Tree']:
		root = TreeBuilder(path=())
		for (path, name) in (
			((15, 2), 'Exchange Server 2019'),
			((15, 1), 'Exchange Server 2016'),
			((15, 0), 'Exchange Server 2013'),
			((14,), 'Exchange Server 2010'),
			((8,), 'Exchange Server 2007'),
			((6, 5), 'Exchange Server 2003'),
			((6, 0), 'Exchange 2000 Server'),
			((5, 5), 'Exchange Server 5.5'),
			((5, 0), 'Exchange Server 5.0'),
			((4, 0), 'Exchange Server 4.0'),
		):
			root._insert_name(path, name)
		for version in versions:
			root._insert(version.num_code, version)
		return list(root._gather_top_trees())


# raw https://github.com/MicrosoftDocs/OfficeDocs-Exchange/blob/public/Exchange/ExchangeServer/new-features/build-numbers-and-release-dates.md
ms_release_list = requests.get('https://raw.githubusercontent.com/MicrosoftDocs/OfficeDocs-Exchange/public/Exchange/ExchangeServer/new-features/build-numbers-and-release-dates.md')
versions = list(Version.scan(ms_release_list.text))

trees = TreeBuilder.from_versions(versions)

with open('versions.yaml', mode='w') as f:
	yaml.dump(trees, stream=f)

with open('versions.html', mode='w') as f:
	f.write("""<!DOCTYPE html>
<html lang="en">
	<head>
		<meta charset="utf-8">
		<link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.4.1/css/bootstrap.min.css" integrity="sha384-Vkoo8x4CGsO3+Hhxv8T/Q5PaXtkKtu6ug5TOeNV6gBiFeWPGFN9MuhOf23Q9Ifjh" crossorigin="anonymous">
		<script src="https://code.jquery.com/jquery-3.4.1.slim.min.js" integrity="sha384-J6qa4849blE2+poT4WnyKhv5vZF5SrPo0iEjwBvKU7imGFAV0wwj1yYfoRSJoZ+n" crossorigin="anonymous"></script>
		<script src="https://cdn.jsdelivr.net/npm/popper.js@1.16.0/dist/umd/popper.min.js" integrity="sha384-Q6E9RHvbIyZFJoft+2mJbHaEWldlvI9IOYy5n3zV9zzTtmI3UksdQRVvoxMfooAo" crossorigin="anonymous"></script>
		<script src="https://stackpath.bootstrapcdn.com/bootstrap/4.4.1/js/bootstrap.min.js" integrity="sha384-wfSDF2E50Y2D1uUdj0O3uMBJnjuUD4Ih7YwaYd1iqfktj0Uod8GCExl3Og8ifwB6" crossorigin="anonymous"></script>
		<meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
		<title>Exchange versions</title>
	</head>
	<body><div class="container-fluid">
		<h1>Exchange versions</h1>
		<button class="btn btn-primary mb-2" type="button" data-toggle="collapse" data-target=".vt-collapse-dead" aria-expanded="true">Toggle old versions</button>
		Also see <a href="https://github.com/stbuehler/exchange-version-check">project on github</a>.
		<table class="table table-striped table-responsive" id="vt">
			<thead class="thead-dark"><tr><th scope="col">Name</th><th scope="col">Version</th><th scope="col">Latest Release</th></tr></thead>
""")
	for tree in trees:
		tree.html_table(f)
	f.write("""		</table>
	</div></body>
</html>
""")

with open('alive.json', mode='w') as f:
	versions = [
		v.short_code
		for tree in trees
		for v in tree.gather_alive_versions()
	]
	json.dump(versions, f)
