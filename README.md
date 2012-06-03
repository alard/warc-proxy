WARC proxy for browsing the contents of a WARC file.

(This must become much easier.)

1. Find a WARC file.
2. Install the Python Twisted library (http://twistedmatrix.com/trac/wiki/Downloads). On Ubuntu or Debian: <code>sudo apt-get install python-twisted</code>
3. Check out the code: <code>git clone https://github.com/alard/warc-proxy</code>
4. Run the proxy: <code>python warcproxy.py ${THEWARCFILE}</code>
5. Set the HTTP proxy of your browser to <code>localhost</code> port <code>8000</code>
6. Visit <code>http://warc/</code> and click on an URL

