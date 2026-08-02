from fastapi import APIRouter

from app.api.v1.accounts.router import router as accounts_router
from app.api.v1.categories.router import router as categories_router
from app.api.v1.import_review.router import router as import_review_router
from app.api.v1.imports.router import router as imports_router
from app.api.v1.manual_ledger.router import router as manual_ledger_router
from app.api.v1.properties.router import router as properties_router
from app.api.v1.reports.router import router as reports_router
from app.api.v1.session.router import router as session_router
from app.api.v1.transaction_rules.router import router as transaction_rules_router

router = APIRouter(prefix="/v1")
router.include_router(accounts_router)
router.include_router(categories_router)
router.include_router(imports_router)
router.include_router(import_review_router)
router.include_router(manual_ledger_router)
router.include_router(properties_router)
router.include_router(reports_router)
router.include_router(session_router)
router.include_router(transaction_rules_router)
