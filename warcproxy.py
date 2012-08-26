import os
import os.path
import cPickle
import re
from collections import OrderedDict
from contextlib import contextmanager

import tornado.httpserver
import tornado.ioloop
import tornado.template
import tornado.web

from hanzo.warctools import WarcRecord
from hanzo.httptools import RequestMessage, ResponseMessage


class WarcProxy(object):
  def __init__(self):
    self.warc_files = set()
    self.indices = {}

  def load_warc_file(self, path):
    if not path in self.warc_files:
      self.warc_files.add(path)
      idx_file = "%s.idx" % path

      if os.path.exists(idx_file) and os.path.getmtime(idx_file) >= os.path.getmtime(path):
        with open(idx_file, "rb") as f:
          records = cPickle.load(f)
      
      else:
        records = OrderedDict()
        warc = WarcRecord.open_archive(path, gzip="auto")
        for (offset, record, errors) in warc.read_records(limit=None):
          if record and record.type == WarcRecord.RESPONSE and record.content[0] == ResponseMessage.CONTENT_TYPE:
            records[record.uri] = offset
        warc.close()

        with open(idx_file, "wb") as f:
          cPickle.dump(records, f)

      print "Indexed. Found "+str(len(records))+" URLs"

      self.indices[path] = records

    return len(self.indices[path])

  def unload_warc_file(self, path):
    self.warc_files.discard(path)
    del self.indices[path]

  def iteruris(self):
    for uris in self.indices.itervalues():
      for uri in uris.iterkeys():
        yield uri

  @contextmanager
  def warc_record_for_uri(self, uri):
    found = False
    for (path, offsets) in self.indices.iteritems():
      if uri in offsets:
        warc = WarcRecord.open_archive(path, gzip="auto")
        warc.seek(offsets[uri])

        for record in warc.read_records(limit=1, offsets=offsets[uri]):
          found = True
          yield record

        warc.close()

    if not found:
      yield None


class WarcProxyWithWeb(object):
  WEB_RE = re.compile(r"^http://(?P<host>warc)(?P<uri>/.*)$")

  def __init__(self, proxy_handler, web_handler):
    self.proxy_handler = proxy_handler
    self.web_handler = web_handler

  def __call__(self, request):
    """Called by HTTPServer to execute the request."""
    web_match = re.match(self.WEB_RE, request.uri)
    if web_match:
      request.host = web_match.group("host")
      request.uri = web_match.group("uri")
      request.path, sep, query = request.uri.partition("?")
      self.web_handler.__call__(request)

    else:
      with self.proxy_handler.warc_record_for_uri(request.uri) as record:
        if record:
          print "Serving %s from WARC" % request.uri
          request.write(record[1].content[1])
        else:
          print "Could not find %s in WARC" % request.uri
          request.write("HTTP/1.0 404 Not Found\r\nContent-Type: text/plain\r\nContent-Length: 12\r\n\r\nNot Found.\r\n")
      request.finish()


class FileBrowserHandler(tornado.web.RequestHandler):
  def get(self):
    cur_dir = self.get_argument("path", None)

    if not cur_dir or not os.path.isdir(cur_dir):
      self.redirect("?path=%s" % os.getcwd())
      return

    try:
      files = os.listdir(cur_dir)
    except OSError:
      files = []

    files.sort()
    files = [{
      "name":   f,
      "path":   os.path.join(cur_dir, f),
      "url":    ("?path=%s" % tornado.escape.url_escape(os.path.join(cur_dir, f))),
      "isdir":  os.path.isdir(os.path.join(cur_dir, f)),
      "iswarc": re.match(r".+\.warc(\.gz)?$", f)
    } for f in files ]

    cur_dir_parts = []
    part = "X"
    while part:
      parent_dir, part = os.path.split(cur_dir)
      cur_dir_parts.append({ "name":part, "path":cur_dir, "url":("?path=%s" % tornado.escape.url_escape(cur_dir)) })
      cur_dir = parent_dir
    cur_dir_parts.reverse()

    self.render("browse.html", cur_dir_parts=cur_dir_parts, files=files)


class MainHandler(tornado.web.RequestHandler):
  def get(self):
    self.write("Hello, world.")


class WarcIndexHandler(tornado.web.RequestHandler):
  def initialize(self, warc_proxy):
    self.warc_proxy = warc_proxy

  def get(self):
    self.write("<ul>")
    for uri in self.warc_proxy.iteruris():
      self.write('<li><a href="%s">%s</a></li>' % (uri, uri))
    self.write("</ul>")


class WarcHandler(tornado.web.RequestHandler):
  def initialize(self, warc_proxy):
    self.warc_proxy = warc_proxy

  def post(self, action):
    if action == "load":
      path = self.get_argument("path")
      print "Loading " + path
      num_records = self.warc_proxy.load_warc_file(path)
      self.write("Indexed %s. Found %d URLs." % (path, num_records))
    elif action == "unload":
      print "Unloading " + self.get_argument("path")
      self.warc_proxy.unload_warc_file(self.get_argument("path"))


warc_proxy = WarcProxy()
web_application = tornado.web.Application([
  (r"/", MainHandler),
  (r"/browse", FileBrowserHandler),
  (r"/(load|unload)-warc", WarcHandler, { "warc_proxy":warc_proxy }),
  (r"/index", WarcIndexHandler, { "warc_proxy":warc_proxy })
], debug=True)

my_application = WarcProxyWithWeb(warc_proxy, web_application)

if __name__ == "__main__":
  http_server = tornado.httpserver.HTTPServer(my_application)
  http_server.listen(8000)
  tornado.ioloop.IOLoop.instance().start()

