"""Register every SQLAlchemy model for standalone commands."""

from app.features.accounts import models as account_models  # noqa: F401
from app.features.categories import models as category_models  # noqa: F401
from app.features.chat_integrations import models as chat_integration_models  # noqa: F401
from app.features.debts import models as debt_models  # noqa: F401
from app.features.imports import models as import_models  # noqa: F401
from app.features.ledger import models as ledger_models  # noqa: F401
from app.features.properties import models as property_models  # noqa: F401
from app.features.transaction_rules import models as transaction_rule_models  # noqa: F401
from app.features.users import models as user_models  # noqa: F401
from app.features.workspaces import models as workspace_models  # noqa: F401
