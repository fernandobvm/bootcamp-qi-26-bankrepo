from dtos.formatters import bank_datetime, money
from models import Account


class AccountDTO:
    @staticmethod
    def obj_to_dict(account: Account) -> dict:
        return {
            "account_id": str(account.id),
            "customer_id": str(account.customer_id),
            "balance": money(account.balance),
            "status": account.status,
            "created_at": bank_datetime(account.created_at),
            "updated_at": bank_datetime(account.updated_at),
        }
