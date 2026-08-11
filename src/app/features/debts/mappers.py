from app.features.debts.schemas import DebtSummaryDto, DebtCapabilitiesDto, DebtStatus
from app.features.accounts.schemas import AccountType
from app.features.accounts.repository import AccountDirectoryRow



class DebtMapper:
    @staticmethod
    def from_account(account: AccountDirectoryRow) -> DebtSummaryDto:
        credit_limit = None
        available_credit = None
        due_date = None

        if account.account_type in (AccountType.CREDIT_CARD, AccountType.MORTGAGE):
            credit_limit = None
            available_credit = None
            due_date = None

        return DebtSummaryDto( 
            id=account.id,
            kind=account.account_type,
            name=account.name,
            currency=account.currency,
            balance=account.confirmed_entry_total,
            principal_outstanding=abs(account.confirmed_entry_total),
            credit_limit=credit_limit,
            available_credit=available_credit,
            due_date=due_date,
            status=DebtStatus.resolve(
                outstanding=abs(account.confirmed_entry_total), due_date=due_date
                ),
            capabilities=DebtCapabilitiesDto.resolve(
                can_write=True,
                is_active=account.is_active,
                outstanding=abs(account.confirmed_entry_total),
                has_payment_account=True
            )
        )
