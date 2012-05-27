# Copyright 2012 Charles Blaxland
# This file is part of rdio-xbmc.
#
# rdio-xbmc is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# rdio-xbmc is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with rdio-xbmc.  If not, see <http://www.gnu.org/licenses/>.

from urlparse import urlparse, parse_qs
from t0mm0.common.addon import Addon
from t0mm0.common.net import Net
import CommonFunctions
from rdioapi import Rdio
from rdiostream import get_rtmp_info


class RdioApi:
  _STATE_FILE_NAME = 'rdio-state.json'
  _RDIO_DOMAIN = 'localhost'
  
  def __init__(self, addon):
    self._addon = addon
    self._net = Net()
    self._state = addon.load_data(self._STATE_FILE_NAME)
    if not self._state:
      addon.log_debug("Persistent auth state not loaded")
      self._state = {'rdio_api': {'auth_state': {}}, 'playback_token': None}
    else:
      addon.log_debug("Loaded persistent auth state")

    apikey = addon.get_setting('apikey')
    addon.log_debug("Connecting to Rdio with apikey " + apikey)
    self._rdio = Rdio(apikey, addon.get_setting('apisecret'), self._state['rdio_api'])
    if not self._rdio.authenticated:
      self._authenticate()
  
    addon.log_notice("Connected successfully to Rdio with apikey " + apikey)
      
  def _authenticate(self):
    self._addon.log_notice("Authenticating to Rdio")
    auth_url = self._rdio.begin_authentication('oob')
    parsed_auth_url = urlparse(auth_url)
    url_base = "%s://%s" % (parsed_auth_url.scheme, parsed_auth_url.netloc)

    self._addon.log_notice("Authorizing OAuth token " + auth_url)
    html = self._net.http_GET(auth_url).content
    login_path = CommonFunctions.parseDOM(html, 'form', {'name': 'login'}, 'action')
    if login_path:
      login_url = url_base + login_path[0]
      username = self._addon.get_setting('username')
      password = self._addon.get_setting('password')
      self._addon.log_notice("Logging in to Rdio as %s using URL %s" % (username, login_url))
      html = self._net.http_POST(login_url, {'username': username, 'password': password}).content

    oauth_token = CommonFunctions.parseDOM(html, 'input', {'name': 'oauth_token'}, 'value')[0]
    verifier = CommonFunctions.parseDOM(html, 'input', {'name': 'verifier'}, 'value')[0]
    
    self._addon.log_notice("Approving oauth token %s with pin %s" % (oauth_token, verifier))
    self._net.http_POST(auth_url, {'oath_token': oauth_token, 'verifier': verifier, 'approve': ''})
    
    self._addon.log_notice("Verifying OAuth token on Rdio API with pin " + verifier)
    self._rdio.complete_authentication(verifier)

    self._addon.log_notice("Getting playback token")
    self._state['playback_token'] = self.call('getPlaybackToken', domain=self._RDIO_DOMAIN)
    self._addon.log_notice("Got playback token: " + self._state['playback_token'])
    
    self._addon.save_data(self._STATE_FILE_NAME, self._state)
    self._addon.log_notice("Successfully authenticated to Rdio")
    
  def resolve_playback_url(self, key):
    rtmp_info = get_rtmp_info(self._RDIO_DOMAIN, self.get_playback_token(), key)
    stream_url = rtmp_info['rtmp']
    for key, value in rtmp_info.items():
      stream_url += '' if key == 'rtmp' else ' %s=%s' % (key, value)

    self._addon.log_debug("Resolved playback URL for key '%s' to %s" % (key, stream_url))
    return stream_url

  def call(self, method, **args):
    self._addon.log_debug("Executing Rdio API call '%s' with args %s" % (method, args))
    return self._rdio.call(method, **args)
    
  def get_playback_token(self):
    return self._state['playback_token']


