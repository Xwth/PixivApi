# -*- coding: utf-8 -*-
import os
import sys

import json
import requests
from requests.adapters import HTTPAdapter
from urllib.parse import urlparse

from time import time

from . import __version__

class JsonDict(dict):
	def __getattr__(self, attr):
		try:
			if isinstance(self[attr], dict):
				self[attr] = JsonDict(self[attr])
			elif isinstance(self[attr], list):
				for idx, value in enumerate(self[attr]):
					if isinstance(value, dict):
						self[attr][idx] = JsonDict(value)
			return self[attr]
		except KeyError:
			raise AttributeError(r"'JsonDict' object has no attribute '%s'" % attr)
	def __setattr__(self, attr, value):
		self[attr] = value
	def __delattr__(self, attr):
		if attr in self:
			del self[attr]
		else:
			raise AttributeError(r"'JsonDict' object has no attribute '%s'" % attr)

class Pixiv:
	#ENDPOINTS
	BASE          = 'https://public-api.secure.pixiv.net'
	API_BASE      = BASE     + '/v1%s.json'
	ILLUST        = API_BASE % '/works/{}'
	USERS         = API_BASE % '/users/{}'
	WORKS         = API_BASE % '/users/{}/works'
	SEARCH        = API_BASE % 'search/works'
	LOGIN         = 'https://oauth.secure.pixiv.net/{}'

	def __init__(self):
		self.username = None
		self.password = None

		self.config = {}
		self.headers = {}
		agent = 'Degenerate/{degenerate} Python/{py[0]}.{py[1]} requests/{req}'
		self.user_agent = agent.format(degenerate=__version__, py=sys.version_info, req=requests.__version__)

		self.session = requests.Session()
		self.session.mount('https://', HTTPAdapter(max_retries=3))

	def configure(self, config):
		self.config = config
		self.username = config['login']['username']
		self.password = config['login']['password']

	def _renew_token(self):
		payload = {'username':      self.username,
				   'password':      self.password,
				   'grant_type':    'password',
				   'client_id':     'bYGKuGVw91e0NMfPGp44euvGt59s',
				   'client_secret': 'HP3RmkgAmEGro0gn1x9ioawQE8WMfvLXDz3ZqxpK'
				}
		if hasattr(self, 'data'):
			self.refresh_token = self.data['refresh_token']
			# payload.update({'grant_type': 'refresh_token'})
			payload.update({'refresh_token': self.refresh_token})
		self.data = self.session.post(
				self.LOGIN.format('auth/token'),
				data=payload,
				headers=self.headers
			).json()['response']

	def _req(self, method, path, **params):
		if (
			not hasattr(self, 'data')
			or self.data['expires_in'] <= (time() - 60)
		):
			self._renew_token()
		auth = {'Authorization': 'Bearer {}'.format(
				self.data['access_token'])}
		self.session.headers.update(auth)
		self.session.headers.update({'User-Agent':self.user_agent})
		self.session.headers.update({'Referer':'http://spapi.pixiv.net/'})
		return self.session.request(
			method,
			path,
			params=params
			).json()['response'][0]

	def _post(self, path, **params):
		return self._req('post', path, **params)

	def _get(self, path, **params):
		return self._req('get', path, **params)

	def get_illust(self, illust_id: int):
		payload = {}
		payload.update({**self.config['illust']})
		return self._get(self.ILLUST.format(illust_id), **payload)

	def get_user_works(self, user_id: int):
		payload = {}
		payload.update({**self.config['common']})
		return self._get(self.WORKS.format(user_id), **payload)

	def get_user(self, user_id: int):
		payload = {}
		payload.update({**self.config['common']})
		return self._get(self.USERS.format(user_id), **payload)

	def search_work(self, query: str, **kwargs):
		keywords= 'q','sort','mode','order','period', 'page'
		payload = {}
		payload.update({**self.config['common']})
		for kw in keywords:
			if kw in kwargs and kwargs[kw]:
				payload[kw] = kwargs[kw]
		payload.update({**self.config['search_work']})
		return self._get(self.SEARCH, **payload)

	def _write(self, response, path, file):
		data = []
		for chunk in response.iter_content(1024 * 16):
			data.append(chunk)
		if not os.path.exists(path):
			os.makedirs(path)
		with open(os.path.join(path, file), 'wb') as f:
			list(map(f.write, data))

	def _download_gallery(self, illust):
		path = os.path.join('images',str(illust.user.id), str(illust.id))
		for url in illust.metadata.pages:
			r = self.session.get('{[image_urls][large]}'.format(url))
			file = urlparse(r.url).path.split('/')[-1]
			if r.ok:
				self._write(r, path, file)

	def _download_image(self, illust):
		path = os.path.join('images',str(illust.user.id), str(illust.id))
		url = illust.image_urls
		r = self.session.get('{[large]}'.format(url))
		file = urlparse(r.url).path.split('/')[-1]
		if r.ok:
			self._write(r, path, file)

	def download(self, illust, retry=None):
		illust = JsonDict(illust)
		if illust.is_manga:
			self._download_gallery(illust)
		else:
			self._download_image(illust)
