from fastapi import APIRouter

from app.api.v1.manual_ledger.mutation_routes import router as mutation_router
from app.api.v1.manual_ledger.read_routes import router as read_router

router = APIRouter(tags=["manual-ledger"])
router.include_router(read_router, prefix="/manual-ledger")
router.include_router(mutation_router, prefix="/manual-ledger")
