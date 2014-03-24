from automatron.controller.controller import IAutomatronClientActions
from automatron.core.event import STOP

try:
    import ujson as json
except ImportError:
    import json
import urllib
from twisted.internet import defer
from twisted.python import log
from twisted.web.client import getPage
from zope.interface import classProvides, implements
from automatron.controller.command import IAutomatronCommandHandler
from automatron.controller.plugin import IAutomatronPluginFactory
from automatron_notify import IAutomatronNotifyHandler


SERVICE = 'https://api.pushbullet.com/api'


class AutomatronPushBulletNotifyPlugin(object):
    classProvides(IAutomatronPluginFactory)
    implements(IAutomatronNotifyHandler, IAutomatronCommandHandler)

    name = 'notify_pushbullet'
    priority = 100

    def __init__(self, controller):
        self.controller = controller

    def on_notify(self, server, username, title, body, body_as_html=None):
        return self._on_notify(server, username, title, body)

    @defer.inlineCallbacks
    def _on_notify(self, server, username, title, body):
        api_key = yield self.controller.config.get_user_preference(server, username, 'pushbullet.api_key')
        if not api_key:
            return

        devices = yield self.controller.config.get_user_preference(server, username, 'pushbullet.devices')

        if devices:
            devices = devices.split(',')
        else:
            try:
                result = json.loads((yield getPage(
                    SERVICE + '/devices',
                    headers={
                        'Authorization': 'Basic ' + (api_key + ':').encode('base64').strip(),
                    },
                )))
                devices = [
                    device['iden']
                    for device in result['devices']
                ]
            except Exception as e:
                log.err(e, 'Failed to retrieve PushBullet devices')
                return

        for device in devices:
            config = urllib.urlencode({
                'device_iden': device,
                'type': 'note',
                'title': title,
                'body': body or '',
            })
            try:
                yield getPage(
                    SERVICE + '/pushes',
                    method='POST',
                    postdata=config,
                    headers={
                        'Authorization': 'Basic ' + (api_key + ':').encode('base64').strip(),
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                )
            except Exception as e:
                log.err(e, 'PushBullet request failed')

    def on_command(self, server, user, command, args):
        if command == 'pushbullet':
            self._on_command_pushbullet(server, user, args)
            return STOP

    @defer.inlineCallbacks
    def _on_command_pushbullet(self, server, user, args):
        if not (yield self.controller.config.has_permission(server['server'], None, user, 'pushbullet')):
            self.controller.plugins.emit(
                IAutomatronClientActions['message'],
                server['server'],
                user,
                'You\'re not authorized to use the PushBullet plugin.'
            )
            return

        if not args:
            self.controller.plugins.emit(
                IAutomatronClientActions['message'],
                server['server'],
                user,
                'Syntax: pushbullet <api key> [device identifier...]'
            )
            return

        api_key = args.pop(0)
        devices = ','.join(args)

        username, _ = yield self.controller.config.get_username_by_hostmask(server['server'], user)
        self.controller.config.update_user_preference(server['server'], username, 'pushbullet.api_key', api_key)
        self.controller.config.update_user_preference(server['server'], username, 'pushbullet.devices', devices)
        self.controller.plugins.emit(
            IAutomatronClientActions['message'],
            server['server'],
            user,
            'Updated your PushBullet configuration.'
        )

        defer.returnValue(STOP)
