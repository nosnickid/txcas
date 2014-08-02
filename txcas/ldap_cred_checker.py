
# External modules
from ldaptor.protocols.ldap import ldapclient, ldapsyntax, ldapconnector
from ldaptor.protocols.ldap.ldaperrors import LDAPInvalidCredentials

from twisted.cred import credentials
from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.error import UnauthorizedLogin
from twisted.internet import defer, reactor
from twisted.plugin import IPlugin
from twisted.python import log
from zope.interface import implements


def escape_filter_chars(assertion_value,escape_mode=0):
    """
    This function shamelessly copied from python-ldap module.
    
    Replace all special characters found in assertion_value
    by quoted notation.

    escape_mode
      If 0 only special chars mentioned in RFC 2254 are escaped.
      If 1 all NON-ASCII chars are escaped.
      If 2 all chars are escaped.
    """
    if escape_mode:
        r = []
        if escape_mode==1:
            for c in assertion_value:
                if c < '0' or c > 'z' or c in "\\*()":
                    c = "\\%02x" % ord(c)
                r.append(c)
        elif escape_mode==2:
            for c in assertion_value:
                r.append("\\%02x" % ord(c))
        else:
          raise ValueError('escape_mode must be 0, 1 or 2.')
        s = ''.join(r)
    else:
        s = assertion_value.replace('\\', r'\5c')
        s = s.replace(r'*', r'\2a')
        s = s.replace(r'(', r'\28')
        s = s.replace(r')', r'\29')
        s = s.replace('\x00', r'\00')
    return s


class LDAPSimpleBindChecker(object):

    implements(IPlugin, ICredentialsChecker)
    credentialInterfaces = (credentials.IUsernamePassword,)


    def __init__(self, host, port, basedn, binddn, bindpw, query_template='(uid=%(username)s)'):
        self._host = host
        self._port = port
        self._basedn = basedn
        self._binddn = binddn
        self._bindpw = bindpw
        self._query_template = query_template


    def requestAvatarId(self, credentials):
        
        def eb(err):
            if not err.check(UnauthorizedLogin, LDAPInvalidCredentials):
                log.err(err)
            raise UnauthorizedLogin()
            
        return self._make_connect(credentials).addErrback(
            eb)

    @defer.inlineCallbacks
    def _make_connect(self, credentials):
        serverip = self._host
        basedn = self._basedn

        c = ldapconnector.LDAPClientCreator(reactor, ldapclient.LDAPClient)
        overrides = {basedn: (serverip, self._port)}
        client = yield c.connect(basedn, overrides=overrides)
        client = yield client.startTLS()
        dn = yield self._get_dn(client, credentials.username)
        yield client.bind(dn, credentials.password)
        
        defer.returnValue(credentials.username)
        
    @defer.inlineCallbacks
    def _get_dn(self, client, username):
        basedn = self._basedn
        binddn = self._binddn
        bindpw = self._bindpw
        query = self._query_template % {'username': escape_filter_chars(username)}
        
        yield client.bind(binddn, bindpw)
        o = ldapsyntax.LDAPEntry(client, basedn)
        results = yield o.search(filterText=query, attributes=['uid'])
        if len(results) != 1:
            raise UnauthorizedLogin()
        entry = results[0]
        defer.returnValue(entry.dn)
        
        
        