# Copyright 2019 Vladimir Istomin
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re
import random
#import cgi
import textwrap
#import urllib
import django.core.validators
import webapp2
from google.appengine.ext import ndb


html_head = textwrap.dedent("""\
<html><body>
<title>URL Shortening App</title>
<h3>URL Shortening App</h3>
""")
html_tail = '</body></html>'


class Hash():
    """Provides a method to generate a random hash from a set of characters"""

    codeset = '23456789abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ-_/.'
    base = len(codeset)

    @classmethod
    def create_key(self):
	"""Creates a new random key"""
	tries = 5
	while tries > 0:
	    tries -= 1
	    urlShort = self.encode()
            urlObj = Url.get_by_id(urlShort)
	    try:
		dummy = urlObj.long
	    except:
		return urlShort
        return ''

    @classmethod
    def encode(self):
        converted = ''
	n = int(random.random()*10000000)
        while n > 0:
            i = int(n % self.base)
            converted += self.codeset[i:i+1]
            n = int(n/self.base)
        return converted


class Url(ndb.Model):
    """Models an individual URL entry with contents, count, and date"""
    long = ndb.StringProperty()
    count = ndb.IntegerProperty()
    dtCreated = ndb.DateTimeProperty(auto_now_add=True)



class Hit(ndb.Model):
    """Models an entry to track visits"""
    dtVisited = ndb.DateTimeProperty(auto_now_add=True)

    @classmethod
    def get_hits(self, ancestor_key):
        return self.query(ancestor=ancestor_key).order(-self.dtVisited)


def mainForm(note='', short='', long=''):
    """Shows the form to enter long URL and optional key"""

    return html_head + textwrap.dedent("""\
<form action="/put" method="post">{note}
  <div>
    Short key (optional):<input name="short" value="{short}">
  </div>
    Long URL*:<br><textarea name="long" rows="4" cols="80">{long}</textarea>
  <div>
    <input type="submit" value="Create a short URL">
  </div>
</form>
""").format(note=note, short=short, long=long) \
      + html_tail


class MainPage(webapp2.RequestHandler):
    """Given an existing short key redirects to the long URL.  Else shows form"""

    def get(self):
	try:
	    urlKey = self.request.path[1:]
            urlObj = Url.get_by_id(urlKey)
            self.redirect(str(urlObj.long))
	    urlObj.count += 1
	    urlObj.put()
	    Hit(parent=ndb.Key("Url", urlKey)).put()
	except:
            self.response.out.write(mainForm())


class StatsPage(webapp2.RequestHandler):
    """Shows statistics for short key / long URL pair"""

    def get(self):
	try:
	    urlKey = self.request.path[7:]
            urlObj = Url.get_by_id(urlKey)
  	    urlLong = str(urlObj.long)
	    hits = Hit.get_hits(ndb.Key("Url", urlKey)).fetch()
            self.response.write(html_head + '<P><b>Statistics</b></P>')
            self.response.write('<p>Short key: '+ urlKey)
            self.response.write('<p>Target URL: '+ urlLong)
            self.response.write('<p>Created: '+ str(urlObj.dtCreated))
            self.response.write('<p>Visited: '+ str(urlObj.count) +' times</p>')
            # reserved for graphing daily visits
	    #for hit in hits:
            #    self.response.write(hit.dtVisited)
            #    self.response.write('<br>')
            self.response.write(html_tail)
	except Exception as e:
            self.response.write(mainForm(
	      '<p>Key does not exist.  Create it.</p>',
	      urlKey
	    ))


class ProcessForm(webapp2.RequestHandler):
    """Creates a short key for a given URL or shows the form with a notice"""

    def get(self):
        self.redirect('/')

    def post(self):
	# strip white space from the form fields
        urlLong = self.request.get('long').strip()
        keyForm = re.sub(r'\s+', '', self.request.get('short'))
	urlShort = keyForm
        if '' == urlShort:
	    urlShort = Hash.create_key()
	    if '' == urlShort:
                self.response.write(mainForm(
    	          '<p><font color="red">Failed to create key.  Try again.<br></font></p>',
	          keyForm, urlLong
	        ))
	        return
	try:
	    validate = django.core.validators.URLValidator()
	    validate(urlLong)
	except:
            self.response.write(mainForm(
	      '<p><font color="red">URL is invalid.  Try another.<br></font></p>',
	      keyForm, urlLong
	    ))
	    return
	try:
            urlObj = Url.get_by_id(urlShort)
	    try:
		dummy = urlObj.long
                self.response.write(mainForm('<p><font color="red">This key exists.  Try another.<br></font></p>', keyForm, urlLong))
	    except:
		try:
                    urlObj = Url.query(Url.long == urlLong).get()
		    if urlLong == str(urlObj.long):
                        urlText = self.request.host_url + '/' + str(urlObj.key.id())
			urlLink = '<a href="{a}">{a}</a>'.format(a=urlText)
                        self.response.write(
			  mainForm(
			    '<p><font color="red">This URL exists</font> under {}<br></p>Try another.<p>'.format(urlLink),
			    keyForm, urlLong)
			  )
		except Exception as e:
		    # time to create a new entry and show results
		    try:
                        urlNew = Url( id=urlShort, long=urlLong, count=0 )
                        urlNew.put()
                        urlText = self.request.host_url + '/' + urlShort
                        self.response.write(html_head + 'New short URL: <a href="{a}">{a}</a>'.format(a=urlText))
                        urlStats = self.request.host_url + '/stats/' + urlShort
                        self.response.write('<p>URL to check stats: <a href="{a}">{a}</a>'.format(a=urlStats))
                        self.response.write(html_tail)
                    except Exception as e:
                        self.response.write('<p><font color="red">Error: <br>{e}</font></p>'.format(e=e))
	except Exception as e:
	    # catch unknown exceptions
            self.response.write('<p><font color="red">Error: <br>{e}</font></p>'.format(e=e)),


app = webapp2.WSGIApplication([
    ('/put', ProcessForm),
    ('/stats/.*', StatsPage),
    ('/.*', MainPage)
], debug=True)
