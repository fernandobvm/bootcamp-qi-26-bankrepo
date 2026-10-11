from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from tests.utils import BankApi, PayloadGenerator, RequestGenerator

FREE_TRANSFERS_PER_MONTH = 5


def two_accounts(balance_out: str, balance_in: str = "0.00") -> tuple:
    return BankApi.create_account(balance=balance_out), BankApi.create_account(balance=balance_in)


def transfer(account_out: str, account_in: str, value: str) -> dict:
    status, response = RequestGenerator.POST_transfer(
        account_out, PayloadGenerator.create_transfer_payload(account_in, value)
    )
    assert status == 201, response
    return response


def use_free_transfers(account_out: str, account_in: str) -> None:
    for _ in range(FREE_TRANSFERS_PER_MONTH):
        assert transfer(account_out, account_in, "1.00")["fee"] == "0.00"


class TestTransfer:
    def test_moves_the_value_between_accounts(self):
        account_out, account_in = two_accounts("500.00")

        response = transfer(account_out, account_in, "200.00")

        assert response["value"] == "200.00"
        assert response["balance_after"] == "300.00"
        assert BankApi.balance(account_out) == "300.00"
        assert BankApi.balance(account_in) == "200.00"

    def test_insufficient_balance_changes_nothing(self):
        account_out, account_in = two_accounts("100.00", "50.00")

        status, response = RequestGenerator.POST_transfer(
            account_out, PayloadGenerator.create_transfer_payload(account_in, "150.00")
        )

        assert status == 422
        assert response["code"] == "EB001008"
        assert BankApi.balance(account_out) == "100.00"
        assert BankApi.balance(account_in) == "50.00"
        assert len(BankApi.statement(account_out)) == 1

    def test_same_key_same_body_returns_the_original(self):
        account_out, account_in = two_accounts("500.00")
        payload = PayloadGenerator.create_transfer_payload(account_in, "200.00")

        first_status, first = RequestGenerator.POST_transfer(account_out, payload)
        second_status, second = RequestGenerator.POST_transfer(account_out, payload)

        assert first_status == second_status == 201
        assert second == first
        assert BankApi.balance(account_out) == "300.00"
        assert BankApi.balance(account_in) == "200.00"

    def test_replay_of_a_paid_transfer_charges_the_fee_once(self):
        account_out, account_in = two_accounts("500.00")
        use_free_transfers(account_out, account_in)
        payload = PayloadGenerator.create_transfer_payload(account_in, "200.00")

        _, first = RequestGenerator.POST_transfer(account_out, payload)
        second_status, second = RequestGenerator.POST_transfer(account_out, payload)

        assert second_status == 201
        assert second == first
        assert first["fee"] == "2.00"
        assert BankApi.balance(account_out) == "293.00"
        assert BankApi.count_in_statement(account_out, "FEE") == 1

    def test_same_amount_written_differently_is_the_same_request(self):
        account_out, account_in = two_accounts("500.00")
        key = str(uuid4())

        RequestGenerator.POST_transfer(account_out, PayloadGenerator.create_transfer_payload(account_in, "200", key))
        status, _ = RequestGenerator.POST_transfer(
            account_out, PayloadGenerator.create_transfer_payload(account_in.upper(), "200.00", key)
        )

        assert status == 201
        assert BankApi.balance(account_out) == "300.00"

    def test_same_key_other_body_is_conflict(self):
        account_out, account_in = two_accounts("500.00")
        other_account = BankApi.create_account()
        key = str(uuid4())
        RequestGenerator.POST_transfer(account_out, PayloadGenerator.create_transfer_payload(account_in, "200.00", key))

        for payload in [
            PayloadGenerator.create_transfer_payload(account_in, "100.00", key),
            PayloadGenerator.create_transfer_payload(other_account, "200.00", key),
        ]:
            status, response = RequestGenerator.POST_transfer(account_out, payload)
            assert status == 409
            assert response["code"] == "EB001007"

        assert BankApi.balance(account_out) == "300.00"

    def test_unknown_destination_keeps_the_origin_untouched(self):
        account_out = BankApi.create_account(balance="100.00")

        for account_in in [str(uuid4()), "nao-e-um-uuid"]:
            status, response = RequestGenerator.POST_transfer(
                account_out, PayloadGenerator.create_transfer_payload(account_in, "10.00")
            )
            assert status == 404, account_in
            assert response["code"] == "EB001005"

        assert BankApi.balance(account_out) == "100.00"

    def test_unknown_origin_is_not_found(self):
        account_in = BankApi.create_account()

        status, response = RequestGenerator.POST_transfer(
            str(uuid4()), PayloadGenerator.create_transfer_payload(account_in, "10.00")
        )

        assert status == 404
        assert response["code"] == "EB001002"

    def test_cannot_transfer_to_itself(self):
        account_id = BankApi.create_account(balance="100.00")

        status, response = RequestGenerator.POST_transfer(
            account_id, PayloadGenerator.create_transfer_payload(account_id, "10.00")
        )

        assert status == 422
        assert response["code"] == "EB001009"
        assert BankApi.balance(account_id) == "100.00"

    def test_both_accounts_must_be_active(self):
        for suspended_side in ["out", "in"]:
            account_out, account_in = two_accounts("100.00")
            if suspended_side == "out":
                BankApi.set_status(account_out, "SUSPENSA")
            else:
                BankApi.set_status(account_in, "SUSPENSA")

            status, response = RequestGenerator.POST_transfer(
                account_out, PayloadGenerator.create_transfer_payload(account_in, "10.00")
            )

            assert status == 409, suspended_side
            assert response["code"] == "EB001006"

    def test_refuses_invalid_values(self):
        account_out, account_in = two_accounts("100.00")

        for value in ["0", "0.00", "-1.00", "1.001", "abc", 50]:
            status, response = RequestGenerator.POST_transfer(
                account_out, PayloadGenerator.create_transfer_payload(account_in, value)
            )
            assert status == 400, f"value={value!r} deveria ser recusado"
            assert response["code"] == "EB000001"

    def test_requires_destination_and_key(self):
        account_out, account_in = two_accounts("100.00")

        for missing_field in ["account_id_in", "idempotency_key"]:
            payload = PayloadGenerator.create_transfer_payload(account_in, "10.00")
            del payload[missing_field]

            status, response = RequestGenerator.POST_transfer(account_out, payload)
            assert status == 400, missing_field
            assert response["code"] == "EB000001"


class TestTransferFee:
    def test_first_five_of_the_month_are_free_and_the_sixth_pays(self):
        account_out, account_in = two_accounts("100.00")

        for _ in range(FREE_TRANSFERS_PER_MONTH):
            response = transfer(account_out, account_in, "10.00")
            assert response["fee"] == "0.00"
            assert response["fee_transaction_id"] is None
            assert response["total_debited"] == "10.00"

        assert BankApi.balance(account_out) == "50.00"
        assert BankApi.count_in_statement(account_out, "FEE") == 0

        # 1% de R$ 10,00 seria R$ 0,10: vale o mínimo.
        sixth = transfer(account_out, account_in, "10.00")
        assert sixth["fee"] == "1.00"
        assert sixth["total_debited"] == "11.00"
        assert BankApi.balance(account_out) == "39.00"
        assert BankApi.balance(account_in) == "60.00"

    def test_percentage_above_the_minimum(self):
        """Débito + tarifa numa conta, crédito na outra — as três escritas de A2 p.34."""
        account_out, account_in = two_accounts("1000.00")
        use_free_transfers(account_out, account_in)

        response = transfer(account_out, account_in, "500.00")

        assert response["fee"] == "5.00"
        assert response["total_debited"] == "505.00"
        assert BankApi.balance(account_out) == "490.00"
        assert BankApi.balance(account_in) == "505.00"

    def test_percentage_rounds_to_the_nearest_cent(self):
        account_out, account_in = two_accounts("1000.00")
        use_free_transfers(account_out, account_in)

        assert transfer(account_out, account_in, "123.45")["fee"] == "1.23"
        assert transfer(account_out, account_in, "150.50")["fee"] == "1.51"

    def test_fee_is_its_own_line_in_the_statement(self):
        account_out, account_in = two_accounts("500.00")
        use_free_transfers(account_out, account_in)

        response = transfer(account_out, account_in, "200.00")

        fee_line, transfer_line = BankApi.statement(account_out)[:2]

        assert fee_line["type"] == "FEE"
        assert fee_line["direction"] == "DEBITO"
        assert fee_line["value"] == "2.00"
        assert fee_line["transaction_id"] == response["fee_transaction_id"]
        assert fee_line["related_transaction_id"] == response["transaction_id"]
        assert fee_line["balance_after"] == "293.00"

        assert transfer_line["type"] == "TRANSFER"
        assert transfer_line["direction"] == "DEBITO"
        assert transfer_line["counterparty_account_id"] == account_in
        assert transfer_line["balance_after"] == "295.00"

        credit_line = BankApi.statement(account_in)[0]
        assert credit_line["type"] == "TRANSFER"
        assert credit_line["direction"] == "CREDITO"
        assert credit_line["value"] == "200.00"
        assert credit_line["counterparty_account_id"] == account_out

    def test_balance_must_cover_the_fee_too(self):
        account_out, account_in = two_accounts("105.99")
        use_free_transfers(account_out, account_in)

        status, response = RequestGenerator.POST_transfer(
            account_out, PayloadGenerator.create_transfer_payload(account_in, "100.00")
        )
        assert status == 422
        assert response["code"] == "EB001008"

        BankApi.deposit(account_out, "0.01")
        assert transfer(account_out, account_in, "100.00")["balance_after"] == "0.00"

    def test_refused_transfers_do_not_use_the_allowance(self):
        account_out, account_in = two_accounts("10.00")

        for _ in range(3):
            status, _ = RequestGenerator.POST_transfer(
                account_out, PayloadGenerator.create_transfer_payload(account_in, "50.00")
            )
            assert status == 422

        use_free_transfers(account_out, account_in)

    def test_receiving_does_not_use_the_allowance(self):
        """A franquia conta o que a conta MANDA. Quem recebeu seis transferências ainda tem as cinco dela."""
        account_out, account_in = two_accounts("100.00")
        for _ in range(FREE_TRANSFERS_PER_MONTH + 1):
            transfer(account_out, account_in, "1.00")

        assert transfer(account_in, account_out, "1.00")["fee"] == "0.00"


class TestTransferConcurrency:
    def test_concurrent_transfers_never_go_negative(self):
        account_out, account_in = two_accounts("100.00")

        with ThreadPoolExecutor(max_workers=5) as pool:
            results = list(
                pool.map(
                    lambda _: RequestGenerator.POST_transfer(
                        account_out, PayloadGenerator.create_transfer_payload(account_in, "30.00")
                    ),
                    range(5),
                )
            )

        statuses = sorted(status for status, _ in results)
        assert statuses == [201, 201, 201, 422, 422]
        assert BankApi.balance(account_out) == "10.00"
        assert BankApi.balance(account_in) == "90.00"

    def test_last_free_transfer_goes_to_exactly_one_request(self):
        account_out, account_in = two_accounts("100.00")
        for _ in range(FREE_TRANSFERS_PER_MONTH - 1):
            transfer(account_out, account_in, "1.00")

        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(
                pool.map(
                    lambda _: RequestGenerator.POST_transfer(
                        account_out, PayloadGenerator.create_transfer_payload(account_in, "10.00")
                    ),
                    range(3),
                )
            )

        assert [status for status, _ in results] == [201, 201, 201]
        assert sorted(response["fee"] for _, response in results) == ["0.00", "1.00", "1.00"]
        assert BankApi.balance(account_out) == "64.00"

    def test_opposite_transfers_do_not_deadlock(self):
        account_a, account_b = two_accounts("1000.00", "1000.00")

        def send(index: int):
            if index % 2 == 0:
                return RequestGenerator.POST_transfer(account_a, PayloadGenerator.create_transfer_payload(account_b, "10.00"))
            return RequestGenerator.POST_transfer(account_b, PayloadGenerator.create_transfer_payload(account_a, "10.00"))

        with ThreadPoolExecutor(max_workers=10) as pool:
            results = list(pool.map(send, range(20)))

        assert [status for status, _ in results] == [201] * 20

        assert BankApi.balance(account_a) == "995.00"
        assert BankApi.balance(account_b) == "995.00"
