#!/usr/bin/env python
import json
import os
import unittest

from saml2 import BINDING_HTTP_REDIRECT, BINDING_HTTP_POST
from saml2.config import SPConfig
from saml2.entity_category.edugain import COC
from saml2.extension.idpdisc import BINDING_DISCO
from saml2.saml import NAMEID_FORMAT_PERSISTENT, NAME_FORMAT_URI

from svs.saml import SamlSp


def full_test_path(file_path):
    test_dir_path = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(test_dir_path, file_path)


class MetadataMock(object):
    def __init__(self, file):
        with open(file) as f:
            self.data = json.load(f)

    def service(self, entity_id, typ, service, binding=None):
        return self.data[entity_id]


class TestSamlSp(unittest.TestCase):
    BASE = "http://localhost"
    ISSUER = BASE
    SP_ENTITY_ID = "{base}_sp.xml".format(base=BASE)
    ACS_URL = "{base}/acs/redirect".format(base=BASE)
    DISCO_URL = "{base}/disco".format(base=BASE)

    @classmethod
    def setUpClass(cls):
        CONFIG = {
            "name": "InAcademia SP",
            "entityid": TestSamlSp.SP_ENTITY_ID,
            'entity_category': [COC],
            "description": "InAcademia SP",
            "service": {
                "sp": {
                    "required_attributes": ["edupersonaffiliation"],
                    "endpoints": {
                        "assertion_consumer_service": [
                            (TestSamlSp.ACS_URL, BINDING_HTTP_REDIRECT),
                        ],
                        "discovery_response": [
                            (TestSamlSp.DISCO_URL, BINDING_DISCO)
                        ]
                    },
                    "name_id_format": [NAMEID_FORMAT_PERSISTENT]
                },
            },
            "key_file": full_test_path("test_data/certs/key.pem"),
            "cert_file": full_test_path("test_data/certs/cert.pem"),
            "name_form": NAME_FORMAT_URI,
        }

        cls.SP_CONF = SPConfig().load(CONFIG)

    def setUp(self):
        self.SP = SamlSp(None, TestSamlSp.SP_CONF, MetadataMock(full_test_path("test_data/idps.md")),
                         "https://ds.example.com", sign_func=None)

    def test_authn_request(self):
        # Check the correct HTTP-POST binding is used
        idp_entity_id = "idp_post"
        request, binding = self.SP.construct_authn_request(idp_entity_id, self.SP.mds, TestSamlSp.ISSUER,
                                                           self.SP.nameid_policy,
                                                           TestSamlSp.ACS_URL)
        assert request is not None
        assert binding == BINDING_HTTP_POST

        # Check the correct HTTP-Redirect binding is used
        idp_entity_id = "idp_redirect"
        request, binding = self.SP.construct_authn_request(idp_entity_id, self.SP.mds, TestSamlSp.ISSUER,
                                                           self.SP.nameid_policy,
                                                           TestSamlSp.ACS_URL)
        assert request is not None
        assert binding == BINDING_HTTP_REDIRECT

        # Check that HTTP-POST is preferred over HTTP-Redirect
        idp_entity_id = "idp_post_redirect"
        request, binding = self.SP.construct_authn_request(idp_entity_id, self.SP.mds, TestSamlSp.ISSUER,
                                                           self.SP.nameid_policy,
                                                           TestSamlSp.ACS_URL)
        assert request is not None
        assert binding == BINDING_HTTP_POST

    def test_redirect_msg(self):
        idp_entity_id = "idp_redirect"
        msg = self.SP.redirect_to_auth(idp_entity_id, "RELAY_STATE")
        assert msg.status == "303 See Other"

    def test_post_msg(self):
        idp_entity_id = "idp_post"
        msg = self.SP.redirect_to_auth(idp_entity_id, "RELAY_STATE")
        assert msg.status == "200 OK"
        assert "<input type=\"hidden\" name=\"SAMLRequest\"" in msg.message
        assert "<input type=\"hidden\" name=\"RelayState\"" in msg.message

    def test_disco_query(self):
        state = "test_state"
        redirect_url = self.SP.disco_query(state)
        assert redirect_url != "{disco_url}?entityID={entity_id}&return={disco_url}&state={state}".format(
            disco_url=TestSamlSp.DISCO_URL, entity_id=TestSamlSp.SP_ENTITY_ID, state=state)