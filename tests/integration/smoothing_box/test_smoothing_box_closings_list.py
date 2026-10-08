from tests.utils import BankSeed, RequestGenerator


def account_with_closed_days(number_of_days: int):
    account_id, days = BankSeed.build_history(["200.00"] * number_of_days)

    for day in days:
        status, _ = RequestGenerator.POST_smoothing_box_closing(account_id, day.isoformat())
        assert status == 201

    return account_id, days


class TestClosingsList:
    def test_lists_newest_first_with_pagination(self):
        account_id, days = account_with_closed_days(5)

        status, response = RequestGenerator.GET_smoothing_box_closings(account_id, {"limit": "2", "page": "0"})

        assert status == 200
        assert [item["reference_date"] for item in response["data"]] == [days[4].isoformat(), days[3].isoformat()]
        assert response["is_last_page"] is False

        status, response = RequestGenerator.GET_smoothing_box_closings(account_id, {"limit": "2", "page": "2"})
        assert [item["reference_date"] for item in response["data"]] == [days[0].isoformat()]
        assert response["is_last_page"] is True

    def test_filters_by_period(self):
        account_id, days = account_with_closed_days(5)

        status, response = RequestGenerator.GET_smoothing_box_closings(
            account_id, {"start_date": days[1].isoformat(), "end_date": days[2].isoformat()}
        )

        assert status == 200
        assert [item["reference_date"] for item in response["data"]] == [days[2].isoformat(), days[1].isoformat()]

    def test_refuses_inverted_period_and_unknown_params(self):
        account_id, days = account_with_closed_days(1)

        status, _ = RequestGenerator.GET_smoothing_box_closings(
            account_id, {"start_date": "2026-05-10", "end_date": "2026-05-01"}
        )
        assert status == 400

        status, _ = RequestGenerator.GET_smoothing_box_closings(account_id, {"inicio": "2026-05-01"})
        assert status == 400

    def test_get_box_shows_the_rule_for_the_next_closing(self):
        account_id, days = account_with_closed_days(3)

        status, box = RequestGenerator.GET_smoothing_box(account_id)

        assert status == 200
        assert box["last_closed_date"] == days[-1].isoformat()
        assert box["next_reference_date"] == BankSeed.today().isoformat()
        assert box["window_days"] == 3
        assert box["baseline"] == "200.00"
