import urllib
from xml.dom.minidom import parseString
from twisted.internet import defer
from twisted.web.client import getPage
from twisted.python import log
from zope.interface import classProvides, implements
from automatron.backend.command import IAutomatronCommandHandler
from automatron.backend.plugin import IAutomatronPluginFactory
from automatron.core.event import STOP
from automatron_notify import IAutomatronNotifyHandler


SERVICE = 'https://www.notifymyandroid.com/publicapi/notify'


class AutomatronNotifyMyAndroidNotifyPlugin(object):
    classProvides(IAutomatronPluginFactory)
    implements(IAutomatronNotifyHandler, IAutomatronCommandHandler)

    name = 'notify_notifymyandroid'
    priority = 100

    def __init__(self, controller):
        self.controller = controller

    def on_notify(self, server, username, title, body, body_as_html=None):
        return self._on_notify(server, username, title, body, body_as_html)

    @defer.inlineCallbacks
    def _on_notify(self, server, username, title, body, body_as_html):
        api_key = yield self.controller.config.get_user_preference(server, username, 'notifymyandroid.api_key')
        if not api_key:
            return

        data = {
            'apikey': api_key,
            'application': 'Automatron IRC bot',
            'event': title,
            'priority': 0,
        }

        if body_as_html is not None:
            data.update({
                'description': body_as_html,
                'content-type': 'text/html',
            })
        else:
            data.update({
                'description': body or '',
                'content-type': 'text/plain',
            })

        try:
            result = yield getPage(
                SERVICE,
                method='POST',
                postdata=urllib.urlencode(data),
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
            )

            doc = parseString(result)
            for node in doc.documentElement.childNodes:
                if node.nodeType != node.ELEMENT_NODE:
                    continue
                elif node.tagName == 'success':
                    break
                elif node.tagName == 'error':
                    code = node.getAttribute('code')
                    error = node.firstChild.nodeValue
                    raise Exception('Notification failed because of %s (%s)' % (error, code))
            else:
                raise Exception('Invalid XML document received (%s)' % result)
        except Exception as e:
            log.err(e, 'NotifyMyAndroid request failed')

    def on_command(self, server, user, command, args):
        if command == 'notifymyandroid':
            self._on_command_notifymyandroid(server, user, args)
            return STOP

    @defer.inlineCallbacks
    def _on_command_notifymyandroid(self, server, user, args):
        if not (yield self.controller.config.has_permission(server['server'], None, user, 'notifymyandroid')):
            self.controller.message(server['server'], user, 'You\'re not authorized to use the NotifyMyAndroid plugin.')

        if len(args) != 1:
            self.controller.message(server['server'], user, 'Syntax: notifymyandroid <api key>')
            defer.returnValue(STOP)

        api_key = args[0].strip()
        username, _ = yield self.controller.config.get_username_by_hostmask(server['server'], user)
        self.controller.config.update_user_preference(server['server'], username, 'notifymyandroid.api_key', api_key)
        self.controller.message(server['server'], user, 'Updated your NotifyMyAndroid configuration.')
