#
#
#

import logging
from collections import defaultdict

from requests import Session

from octodns import __VERSION__ as octodns_version
from octodns.provider import ProviderException
from octodns.provider.base import BaseProvider
from octodns.record import Record

# TODO: remove __VERSION__ with the next major version release
__version__ = __VERSION__ = '1.0.0'


class DigitalOceanClientException(ProviderException):
    pass


class DigitalOceanClientNotFound(DigitalOceanClientException):
    def __init__(self):
        super().__init__('Not Found')


class DigitalOceanClientUnauthorized(DigitalOceanClientException):
    def __init__(self):
        super().__init__('Unauthorized')


class DigitalOceanClient(object):
    BASE = 'https://api.digitalocean.com/v2'

    def __init__(self, token):
        sess = Session()
        sess.headers.update(
            {
                'Authorization': f'Bearer {token}',
                'User-Agent': f'octodns/{octodns_version} octodns-digitalocean/{__VERSION__}',
            }
        )
        self._sess = sess

    def _request(self, method, path, params=None, data=None):
        url = f'{self.BASE}{path}'
        resp = self._sess.request(method, url, params=params, json=data)
        if resp.status_code == 401:
            raise DigitalOceanClientUnauthorized()
        if resp.status_code == 404:
            raise DigitalOceanClientNotFound()
        resp.raise_for_status()
        return resp

    def domains(self):
        path = '/domains'
        ret = []

        page = 1
        while True:
            data = self._request('GET', path, {'page': page}).json()

            ret += data['domains']
            links = data['links']

            try:
                links['pages']['last']
                page += 1
            except KeyError:
                break

        return ret

    def domain(self, name):
        path = f'/domains/{name}'
        return self._request('GET', path).json()

    def domain_create(self, name):
        # Digitalocean requires an IP on zone creation
        self._request(
            'POST', '/domains', data={'name': name, 'ip_address': '192.0.2.1'}
        )

        # After the zone is created, immediately delete the record
        records = self.records(name)
        for record in records:
            if record['name'] == '' and record['type'] == 'A':
                self.record_delete(name, record['id'])

    def records(self, zone_name):
        path = f'/domains/{zone_name}/records'
        ret = []

        page = 1
        while True:
            data = self._request('GET', path, {'page': page}).json()

            ret += data['domain_records']
            links = data['links']

            # https://developers.digitalocean.com/documentation/v2/#links
            # pages exists if there is more than 1 page
            # last doesn't exist if you're on the last page
            try:
                links['pages']['last']
                page += 1
            except KeyError:
                break

        for record in ret:
            # change any apex record to empty string
            if record['name'] == '@':
                record['name'] = ''

            # change any apex value to zone name
            if record['data'] == '@':
                record['data'] = zone_name

        return ret

    def record_create(self, zone_name, params):
        path = f'/domains/{zone_name}/records'
        # change empty name string to @, DO uses @ for apex record names
        if params['name'] == '':
            params['name'] = '@'

        self._request('POST', path, data=params)

    def record_delete(self, zone_name, record_id):
        path = f'/domains/{zone_name}/records/{record_id}'
        self._request('DELETE', path)


class DigitalOceanProvider(BaseProvider):
    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False
    SUPPORTS_ROOT_NS = True
    SUPPORTS = set(('A', 'AAAA', 'CAA', 'CNAME', 'MX', 'NS', 'TXT', 'SRV'))

    def __init__(self, id, token, *args, **kwargs):
        self.log = logging.getLogger(f'DigitalOceanProvider[{id}]')
        self.log.debug('__init__: id=%s, token=***', id)
        super().__init__(id, *args, **kwargs)
        self._client = DigitalOceanClient(token)

        self._zone_records = {}

    def _data_for_multiple(self, _type, records):
        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            'values': [r['data'] for r in records],
        }

    _data_for_A = _data_for_multiple
    _data_for_AAAA = _data_for_multiple

    def _data_for_CAA(self, _type, records):
        values = []
        for record in records:
            values.append(
                {
                    'flags': record['flags'],
                    'tag': record['tag'],
                    'value': record['data'],
                }
            )
        return {'ttl': records[0]['ttl'], 'type': _type, 'values': values}

    def _data_for_CNAME(self, _type, records):
        record = records[0]
        return {
            'ttl': record['ttl'],
            'type': _type,
            'value': f'{record["data"]}.',
        }

    def _data_for_MX(self, _type, records):
        values = []
        for record in records:
            values.append(
                {
                    'preference': record['priority'],
                    'exchange': f'{record["data"]}.',
                }
            )
        return {'ttl': records[0]['ttl'], 'type': _type, 'values': values}

    def _data_for_NS(self, _type, records):
        values = []
        for record in records:
            values.append(f'{record["data"]}.')
        return {'ttl': records[0]['ttl'], 'type': _type, 'values': values}

    def _data_for_SRV(self, _type, records):
        values = []
        for record in records:
            target = f'{record["data"]}.' if record['data'] != "." else "."
            values.append(
                {
                    'port': record['port'],
                    'priority': record['priority'],
                    'target': target,
                    'weight': record['weight'],
                }
            )
        return {'type': _type, 'ttl': records[0]['ttl'], 'values': values}

    def _data_for_TXT(self, _type, records):
        values = [value['data'].replace(';', '\\;') for value in records]
        return {'ttl': records[0]['ttl'], 'type': _type, 'values': values}

    def zone_records(self, zone):
        if zone.name not in self._zone_records:
            try:
                self._zone_records[zone.name] = self._client.records(
                    zone.name[:-1]
                )
            except DigitalOceanClientNotFound:
                return []

        return self._zone_records[zone.name]

    def list_zones(self):
        self.log.debug('list_zones:')
        domains = [f'{d["name"]}.' for d in self._client.domains()]
        return sorted(domains)

    def populate(self, zone, target=False, lenient=False):
        self.log.debug(
            'populate: name=%s, target=%s, lenient=%s',
            zone.name,
            target,
            lenient,
        )

        values = defaultdict(lambda: defaultdict(list))
        for record in self.zone_records(zone):
            _type = record['type']
            if _type not in self.SUPPORTS:
                self.log.warning(
                    'populate: skipping unsupported %s record', _type
                )
                continue
            values[record['name']][record['type']].append(record)

        before = len(zone.records)
        for name, types in values.items():
            for _type, records in types.items():
                data_for = getattr(self, f'_data_for_{_type}')
                record = Record.new(
                    zone,
                    name,
                    data_for(_type, records),
                    source=self,
                    lenient=lenient,
                )
                zone.add_record(record, lenient=lenient)

        exists = zone.name in self._zone_records
        self.log.info(
            'populate:   found %s records, exists=%s',
            len(zone.records) - before,
            exists,
        )
        return exists

    def _params_for_multiple(self, record):
        for value in record.values:
            yield {
                'data': value,
                'name': record.name,
                'ttl': record.ttl,
                'type': record._type,
            }

    _params_for_A = _params_for_multiple
    _params_for_AAAA = _params_for_multiple
    _params_for_NS = _params_for_multiple

    def _params_for_CAA(self, record):
        for value in record.values:
            yield {
                'data': value.value,
                'flags': value.flags,
                'name': record.name,
                'tag': value.tag,
                'ttl': record.ttl,
                'type': record._type,
            }

    def _params_for_single(self, record):
        yield {
            'data': record.value,
            'name': record.name,
            'ttl': record.ttl,
            'type': record._type,
        }

    _params_for_CNAME = _params_for_single

    def _params_for_MX(self, record):
        for value in record.values:
            yield {
                'data': value.exchange,
                'name': record.name,
                'priority': value.preference,
                'ttl': record.ttl,
                'type': record._type,
            }

    def _params_for_SRV(self, record):
        for value in record.values:
            yield {
                'data': value.target,
                'name': record.name,
                'port': value.port,
                'priority': value.priority,
                'ttl': record.ttl,
                'type': record._type,
                'weight': value.weight,
            }

    def _params_for_TXT(self, record):
        # DigitalOcean doesn't want things escaped in values so we
        # have to strip them here and add them when going the other way
        for value in record.values:
            yield {
                'data': value.replace('\\;', ';'),
                'name': record.name,
                'ttl': record.ttl,
                'type': record._type,
            }

    def _apply_Create(self, change):
        new = change.new
        params_for = getattr(self, f'_params_for_{new._type}')
        for params in params_for(new):
            self._client.record_create(new.zone.name[:-1], params)

    def _apply_Update(self, change):
        self._apply_Delete(change)
        self._apply_Create(change)

    def _apply_Delete(self, change):
        existing = change.existing
        zone = existing.zone
        for record in self.zone_records(zone):
            if (
                existing.name == record['name']
                and existing._type == record['type']
            ):
                self._client.record_delete(zone.name[:-1], record['id'])

    def _apply(self, plan):
        desired = plan.desired
        changes = plan.changes
        self.log.debug(
            '_apply: zone=%s, len(changes)=%d', desired.name, len(changes)
        )

        domain_name = desired.name[:-1]
        try:
            self._client.domain(domain_name)
        except DigitalOceanClientNotFound:
            self.log.debug('_apply:   no matching zone, creating domain')
            self._client.domain_create(domain_name)

        for change in changes:
            class_name = change.__class__.__name__
            getattr(self, f'_apply_{class_name}')(change)

        # Clear out the cache if any
        self._zone_records.pop(desired.name, None)
