# http://stackoverflow.com/questions/3402694/twisted-web-proxy
from twisted.internet import reactor
from twisted.web import http
from twisted.web.proxy import Proxy, ProxyRequest, ProxyClientFactory, ProxyClient
from ImageFile import Parser
from StringIO import StringIO

# class InterceptingProxyClient(ProxyClient):
#   def __init__(self, *args, **kwargs):
#     ProxyClient.__init__(self, *args, **kwargs)

#   def handleHeader(self, key, value):
#     ProxyClient.handleHeader(self, key, value)

#   def handleEndHeaders(self):
#     ProxyClient.handleEndHeaders(self)

#   def handleResponsePart(self, buffer):
#     print buffer
#     ProxyClient.handleResponsePart(self, buffer)

#   def handleResponseEnd(self):
#     ProxyClient.handleResponseEnd(self)

# class InterceptingProxyClientFactory(ProxyClientFactory):
#   protocol = InterceptingProxyClient

# class InterceptingProxyRequest(ProxyRequest):
#   protocols = {'http': InterceptingProxyClientFactory}
#   ports = {"http" : 80}

#   def requestReceived(self, command, path, version):
#     # before
#     print(command, path, version)
#     ProxyRequest.requestReceived(self, command, path, version)

#   def process(self):
#     print("x")
#     print(self.getRequestHostname())
#     ProxyRequest.process(self)

import sys

from hanzo.warctools import WarcRecord
from hanzo.httptools import RequestMessage, ResponseMessage

records = {}

filename = sys.argv[1]

print "Indexing "+filename
warc = WarcRecord.open_archive(sys.argv[1], gzip="auto")
for (offset, record, errors) in warc.read_records(limit=None):
  if record and record.type == WarcRecord.RESPONSE and record.content[0] == ResponseMessage.CONTENT_TYPE:
    records[record.url] = offset
warc.close()
print "Indexed. Found "+str(len(records))+" URLs"

class WarcProxyRequest(http.Request):
  def process(self):
    if self.method == "GET":
      if self.uri == "http://warc/":
        self.setResponseCode(200)
        self.setHeader("Content-Type", "text/html")
        self.write("<html><header><title>WARC index</title></header><body><h1>"+filename+"</h1><p>URLs saved:</p><ul>")
        urls = records.keys()
        urls.sort()
        for url in urls:
          self.write("<li><a href=\""+url+"\">"+url+"</a></li>")
        self.write("</ul></body></html>")

      elif self.uri in records:
        warc = WarcRecord.open_archive(sys.argv[1], gzip="auto")
        offset = records[self.uri]
        warc.seek(offset)

        record = warc.__iter__().next()

        if record:
          message = ResponseMessage(RequestMessage())
          leftover = message.feed(record.content[1])
          message.close()

          print("Serving "+self.uri)
          self.setResponseCode(message.code)
          for (name, value) in message.header.headers:
            self.setHeader(name, value)
          for (name, value) in record.headers:
            self.setHeader(name, value)
          self.write(message.get_body())
        else:
          self.setResponseCode(500)
          self.write("Error retrieving record from WARC.\n")

        warc.close()

      else:
        self.setResponseCode(404)
        self.setHeader("Content-Type", "text/html")
        self.write("<html><header><title>URL not found in WARC</title></header><body><h1>URL not found in "+filename+"</h1><p><a href=\"http://warc/\">Visit http://warc/ for a list of URLs in this file</a></p></body></html>")

    else:
      self.setResponseCode(403)
      self.write("Only GET requests are allowed.\n")

    self.finish()

class WarcProxy(Proxy):
  requestFactory = WarcProxyRequest

factory = http.HTTPFactory()
factory.protocol = WarcProxy

print
print "Change the HTTP proxy of your browser to localhost:8000 and"
print "then visit http://warc/"
print

reactor.listenTCP(8000, factory)
reactor.run()

warc.close()



