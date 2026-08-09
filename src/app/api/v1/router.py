from fastapi import APIRouter

from app.api.v1.account.router import router as account_router
from app.api.v1.accounts.router import router as accounts_router
from app.api.v1.auth.router import router as auth_router
from app.api.v1.categories.router import router as categories_router
from app.api.v1.chat_integrations.router import router as chat_integrations_router
from app.api.v1.dashboard.router import router as dashboard_router
from app.api.v1.debts.router import router as debts_router
from app.api.v1.import_review.router import router as import_review_router
from app.api.v1.imports.router import router as imports_router
from app.api.v1.manual_ledger.router import router as manual_ledger_router
from app.api.v1.properties.router import router as properties_router
from app.api.v1.reports.router import router as reports_router
from app.api.v1.session.router import router as session_router
from app.api.v1.transaction_rules.router import router as transaction_rules_router
from app.api.v1.workspaces.router import router as workspaces_router

router = APIRouter(prefix="/v1")
router.include_router(account_router)
router.include_router(accounts_router)
router.include_router(auth_router)
router.include_router(categories_router)
router.include_router(chat_integrations_router)
router.include_router(dashboard_router)
router.include_router(debts_router)
router.include_router(imports_router)
router.include_router(import_review_router)
router.include_router(manual_ledger_router)
router.include_router(properties_router)
router.include_router(reports_router)
router.include_router(session_router)
router.include_router(transaction_rules_router)
router.include_router(workspaces_router)
