import collections
import logging
import socket
import string
import threading
from hashlib import sha256, md5

import fedmsg
import fedmsg.meta
import fedora.client
import fedora.client.fas2
from dogpile.cache import make_region

CONFIG = fedmsg.config.load_config()
fedmsg.meta.make_processors(**CONFIG)

_cache = make_region(
    key_mangler=lambda key: "fmn.consumer:dogpile:" + key
).configure(**CONFIG['fmn.rules.cache'])

log = logging.getLogger("moksha.hub")

default_url = 'https://admin.fedoraproject.org/accounts/'
creds = CONFIG['fas_credentials']

fasclient = fedora.client.fas2.AccountSystem(
    base_url=creds.get('base_url', default_url),
    username=creds['username'],
    password=creds['password'],
)


def make_fas_cache(**config):
    log.warn("Building the FAS cache into redis.")
    if _cache.get('fas_cache_built'):
        log.warn("FAS cache already built into redis.")
        return

    global fasclient
    timeout = socket.getdefaulttimeout()
    for key in string.ascii_lowercase:
        socket.setdefaulttimeout(600)
        try:
            log.info("Downloading FAS cache for %s*" % key)
            print key
            request = fasclient.send_request(
                '/user/list',
                req_params={'search': '%s*' % key},
                auth=True)
        except fedora.client.ServerError as e:
            log.warning("Failed to download fas cache for %s %r" % (key, e))
            return {}
        finally:
            socket.setdefaulttimeout(timeout)

        log.info("Caching necessary user data")
        for user in request['people']:
            nick = user['ircnick']
            if nick:
                _cache.set(nick, user['username'])

            email = user['email']
            if email:
                _cache.set(email, user['username'])

        del request

    del fasclient
    del fedora.client.fas2
    _cache.set('fas_cache_built', True)


def update_nick(username):
    global fasclient
    try:
        log.info("Downloading FAS cache for %s*" % username)
        request = fasclient.send_request(
            '/user/list',
            req_params={'search': '%s' % username},
            auth=True)
    except fedora.client.ServerError as e:
        log.warning(
            "Failed to download fas cache for %s: %r" % (username, e))
        return {}

    log.info("Caching necessary data for %s" % username)
    for user in request['people']:
        nick = user['ircnick']
        if nick:
            _cache.set(nick, user['username'])

        email = user['email']
        if email:
            _cache.set(email, user['username'])


def update_email(username):
    global fasclient
    try:
        log.info("Downloading FAS cache for %s*" % username)
        request = fasclient.send_request(
            '/user/list',
            req_params={'search': '%s' % username},
            auth=True)
    except fedora.client.ServerError as e:
        log.warning(
            "Failed to download fas cache for %s: %r" % (username, e))
        return {}

    log.info("Caching necessary data for %s" % username)
    for user in request['people']:
        nick = user['ircnick']
        if nick:
            _cache.set(nick, user['username'])

        email = user['email']
        if email:
            _cache.set(email, user['username'])


def nick2fas(nickname, **config):
    result = _cache.get(nickname)
    if not result:
        update_nick(username)
        result = _cache.get(nickname)
    return result


def email2fas(email, **config):
    if email.endswith('@fedoraproject.org'):
        return email.rsplit('@', 1)[0]

    result = _cache.get(email)
    if not result:
        update_email(email)
        result = _cache.get(email)
    return result
