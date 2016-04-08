# -*- coding: utf-8 -*-
from openprocurement.api.models import get_now
from openprocurement.api.validation import validate_patch_bid_data
from openprocurement.api.utils import (
    apply_patch,
    opresource,
    json_view,
    context_unpack,
)
from openprocurement.tender.openua.views.bid import TenderUABidResource as BaseResource


@opresource(name='Tender EU Bids',
            collection_path='/tenders/{tender_id}/bids',
            path='/tenders/{tender_id}/bids/{bid_id}',
            procurementMethodType='aboveThresholdEU',
            description="Tender EU bids")
class TenderBidResource(BaseResource):
    """ Tender EU bids """
    @json_view(permission='view_tender')
    def collection_get(self):
        """Bids Listing

        Get Bids List
        -------------

        Example request to get bids list:

        .. sourcecode:: http

            GET /tenders/4879d3f8ee2443169b5fbbc9f89fa607/bids HTTP/1.1
            Host: example.com
            Accept: application/json

        This is what one should expect in response:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            {
                "data": [
                    {
                        "value": {
                            "amount": 489,
                            "currency": "UAH",
                            "valueAddedTaxIncluded": true
                        }
                    }
                ]
            }

        """
        tender = self.request.validated['tender']
        if self.request.validated['tender_status'] == 'active.tendering':
            self.request.errors.add('body', 'data', 'Can\'t view bids in current ({}) tender status'.format(self.request.validated['tender_status']))
            self.request.errors.status = 403
            return
        return {'data': [i.serialize(self.request.validated['tender_status']) for i in tender.bids]}

    @json_view(permission='view_tender')
    def get(self):
        """Retrieving the proposal

        Example request for retrieving the proposal:

        .. sourcecode:: http

            GET /tenders/4879d3f8ee2443169b5fbbc9f89fa607/bids/71b6c23ed8944d688e92a31ec8c3f61a HTTP/1.1
            Host: example.com
            Accept: application/json

        And here is the response to be expected:

        .. sourcecode:: http

            HTTP/1.0 200 OK
            Content-Type: application/json

            {
                "data": {
                    "value": {
                        "amount": 600,
                        "currency": "UAH",
                        "valueAddedTaxIncluded": true
                    }
                }
            }

        """
        if self.request.authenticated_role == 'bid_owner':
            return {'data': self.request.context.serialize('view')}
        if self.request.validated['tender_status'] == 'active.tendering':
            self.request.errors.add('body', 'data', 'Can\'t view bid in current ({}) tender status'.format(self.request.validated['tender_status']))
            self.request.errors.status = 403
            return
        return {'data': self.request.context.serialize(self.request.validated['tender_status'])}

    @json_view(content_type="application/json", permission='edit_bid', validators=(validate_patch_bid_data,))
    def patch(self):
        """Update of proposal

        Example request to change bid proposal:

        .. sourcecode:: http

            PATCH /tenders/4879d3f8ee2443169b5fbbc9f89fa607/bids/71b6c23ed8944d688e92a31ec8c3f61a HTTP/1.1
            Host: example.com
            Accept: application/json

            {
                "data": {
                    "value": {
                        "amount": 600
                    }
                }
            }

        And here is the response to be expected:

        .. sourcecode:: http

            HTTP/1.0 200 OK
            Content-Type: application/json

            {
                "data": {
                    "value": {
                        "amount": 600,
                        "currency": "UAH",
                        "valueAddedTaxIncluded": true
                    }
                }
            }

        """
        if self.request.authenticated_role != 'Administrator' and self.request.validated['tender_status'] != 'active.tendering':
            self.request.errors.add('body', 'data', 'Can\'t update bid in current ({}) tender status'.format(self.request.validated['tender_status']))
            self.request.errors.status = 403
            return
        tender = self.request.validated['tender']
        if self.request.authenticated_role != 'Administrator' and (tender.tenderPeriod.startDate and get_now() < tender.tenderPeriod.startDate or get_now() > tender.tenderPeriod.endDate):
            self.request.errors.add('body', 'data', 'Bid can be updated only during the tendering period: from ({}) to ({}).'.format(tender.tenderPeriod.startDate and tender.tenderPeriod.startDate.isoformat(), tender.tenderPeriod.endDate.isoformat()))
            self.request.errors.status = 403
            return
        if self.request.authenticated_role != 'Administrator':
            bid_status_to = self.request.validated['data'].get("status", self.request.context.status)
            if bid_status_to != 'pending':
                self.request.errors.add('body', 'bid', 'Can\'t update bid to ({}) status'.format(bid_status_to))
                self.request.errors.status = 403
                return
        value = self.request.validated['data'].get("value") and self.request.validated['data']["value"].get("amount")
        if value and value != self.request.context.get("value", {}).get("amount"):
            self.request.validated['data']['date'] = get_now().isoformat()
        if self.request.context.lotValues:
            lotValues = dict([(i.relatedLot, i.value.amount) for i in self.request.context.lotValues])
            for lotvalue in self.request.validated['data'].get("lotValues", []):
                if lotvalue['relatedLot'] in lotValues and lotvalue.get("value", {}).get("amount") != lotValues[lotvalue['relatedLot']]:
                    lotvalue['date'] = get_now().isoformat()
        self.request.validated['tender'].modified = False
        if apply_patch(self.request, src=self.request.context.serialize()):
            self.LOGGER.info('Updated tender bid {}'.format(self.request.context.id),
                        extra=context_unpack(self.request, {'MESSAGE_ID': 'tender_bid_patch'}))
            return {'data': self.request.context.serialize("view")}
