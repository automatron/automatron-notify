import json
import urllib
from twisted.internet import defer
from twisted.python import log
from twisted.web.client import getPage
from zope.interface import classProvides, implements
from automatron.client import IAutomatronMessageHandler
from automatron.plugin import IAutomatronPluginFactory, STOP
from automatron_notify import IAutomatronNotifyHandler


SERVICE = 'https://api.pushbullet.com/api'


class AutomatronPushBulletNotifyPlugin(object):
    classProvides(IAutomatronPluginFactory)
    implements(IAutomatronNotifyHandler, IAutomatronMessageHandler)

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

    @defer.inlineCallbacks
    def on_message(self, client, user, channel, message):
        if channel != client.nickname or not (message.startswith('pushbullet ') or message == 'pushbullet'):
            return

        if not (yield self.controller.config.has_permission(client.server, None, user, 'pushbullet')):
            client.msg('You\'re not authorized to use the PushBullet plugin.')
            return

        nickname = client.parse_user(user)[0]

        if message == 'pushbullet':
            client.msg(nickname, 'Syntax: pushbullet <api key> [device identifier...]')
            return

        api_key = message.split(' ', 1)[1].strip()
        if ' ' in api_key:
            api_key, devices = api_key.split(' ', 1)
            devices = ','.join(d for d in devices.split(' ') if d)
        else:
            devices = None

        username, _ = yield client.controller.config.get_username_by_hostmask(client.server, user)
        self.controller.config.update_user_preference(client.server, username, 'pushbullet.api_key', api_key)
        self.controller.config.update_user_preference(client.server, username, 'pushbullet.devices', devices)
        client.msg(nickname, 'Updated your PushBullet configuration.')

        defer.returnValue(STOP)
