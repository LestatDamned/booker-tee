from fastapi import APIRouter

from app.api.v1.accounts.router import router as accounts_router
from app.api.v1.import_review.router import router as import_review_router
from app.api.v1.imports.router import router as imports_router
from app.api.v1.manual_ledger.router import router as manual_ledger_router
from app.api.v1.session.router import router as session_router

router = APIRouter(prefix="/v1")
router.include_router(accounts_router)
router.include_router(imports_router)
router.include_router(import_review_router)
router.include_router(manual_ledger_router)
router.include_router(session_router)
