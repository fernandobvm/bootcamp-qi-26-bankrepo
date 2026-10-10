from dtos.formatters import bank_datetime
from models import Account, Customer


class CustomerDTO:
    """O cliente na resposta, sempre com o `account_id` da conta dele."""

    @staticmethod
    def obj_to_dict(customer: Customer, account: Account) -> dict:
        return {
            "customer_id": str(customer.id),
            "account_id": str(account.id),
            "name": customer.name,
            "nationality": customer.nationality,
            "document_number": customer.document_number,
            "email": customer.email,
            "birth_date": customer.birth_date.isoformat(),
            "created_at": bank_datetime(customer.created_at),
        }
