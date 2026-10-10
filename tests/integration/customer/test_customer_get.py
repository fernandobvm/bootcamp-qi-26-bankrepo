from uuid import uuid4

from tests.utils import BankApi, RequestGenerator


class TestCustomerGet:
    def test_returns_customer_with_document_and_account(self):
        created = BankApi.create_customer()

        status, customer = RequestGenerator.GET_customer(created["customer_id"])

        assert status == 200
        assert customer == created

    def test_unknown_customer_is_not_found(self):
        for customer_id in [str(uuid4()), "nao-e-um-uuid"]:
            status, response = RequestGenerator.GET_customer(customer_id)

            assert status == 404, customer_id
            assert response["code"] == "EB001001"
