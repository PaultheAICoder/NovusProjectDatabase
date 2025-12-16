# SQLAlchemy Relationship Safety Guidelines

This document describes how to safely define SQLAlchemy relationships in the Novus Project Database, particularly when multiple foreign key paths exist between models.

## Background

During the implementation of Issues #37-#44, we experienced a production outage caused by an ambiguous SQLAlchemy relationship. This document captures the lessons learned.

## The Problem: Ambiguous Foreign Keys

When a model has multiple foreign keys pointing to the same target model, SQLAlchemy cannot determine which foreign key to use for a relationship. This results in an `AmbiguousForeignKeysError` that causes 500 errors on all API endpoints.

### Example: Contact and Organization

```python
# Contact model has a foreign key to Organization
class Contact(Base):
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))

# Organization model has TWO relationships to Contact
class Organization(Base):
    # Primary contact relationship (via Contact.organization_id)
    contacts: Mapped[list["Contact"]] = relationship(...)

    # Billing contact (a specific contact for billing)
    billing_contact_id: Mapped[UUID | None] = mapped_column(ForeignKey("contacts.id"))
    billing_contact: Mapped["Contact | None"] = relationship(...)
```

This creates an ambiguous path:
- `Organization.contacts` -> uses `Contact.organization_id`
- `Organization.billing_contact` -> uses `Organization.billing_contact_id`

SQLAlchemy cannot infer which FK to use for each relationship.

## The Solution: Explicit `foreign_keys`

**ALWAYS specify `foreign_keys` when multiple FK paths exist between models.**

### Correct Implementation

```python
# In Contact model
class Contact(Base):
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))

    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="contacts",
        foreign_keys=[organization_id],  # EXPLICIT FK
    )

# In Organization model
class Organization(Base):
    billing_contact_id: Mapped[UUID | None] = mapped_column(ForeignKey("contacts.id"))

    contacts: Mapped[list["Contact"]] = relationship(
        "Contact",
        back_populates="organization",
        lazy="selectin",
        foreign_keys="[Contact.organization_id]",  # EXPLICIT FK (string form)
    )

    billing_contact: Mapped["Contact | None"] = relationship(
        "Contact",
        foreign_keys=[billing_contact_id],  # EXPLICIT FK
        lazy="selectin",
    )
```

## When to Use `foreign_keys`

### Always Required
- Model A has FK to Model B AND Model B has FK to Model A
- Model has multiple FKs to the same target model
- Self-referential relationships

### Examples in This Codebase

1. **Organization <-> Contact** (Issue #35)
   - `Contact.organization_id` -> Organization
   - `Organization.billing_contact_id` -> Contact
   - Files: `backend/app/models/organization.py`, `backend/app/models/contact.py`

2. **Project -> User** (multiple FKs)
   - `Project.owner_id` -> User
   - `Project.created_by` -> User
   - `Project.updated_by` -> User
   - File: `backend/app/models/project.py`

## Code Review Checklist

When reviewing PRs that modify SQLAlchemy models:

- [ ] Check if new FK creates multiple paths to same model
- [ ] Verify `foreign_keys` is specified on all affected relationships
- [ ] Test API endpoints after migration (watch for 500 errors)
- [ ] Run full test suite to catch relationship errors

## Detection Commands

```bash
# Find all relationships without explicit foreign_keys
grep -n "relationship(" backend/app/models/*.py | grep -v "foreign_keys"

# Find all foreign key definitions
grep -n "ForeignKey" backend/app/models/*.py

# Find models with multiple FKs to same table
grep -E "ForeignKey\(['\"]" backend/app/models/*.py | cut -d: -f1 | sort | uniq -c | sort -rn
```

## Testing After Model Changes

**MANDATORY** after any model relationship changes:

```bash
# 1. Run migrations
docker exec npd-backend alembic upgrade head

# 2. Restart backend to load model changes
docker compose restart backend

# 3. Test key endpoints
curl http://localhost:6701/health
curl http://localhost:6701/api/v1/projects
curl http://localhost:6701/api/v1/organizations
curl http://localhost:6701/api/v1/contacts

# 4. Run full test suite
cd backend && pytest tests/ -v
```

## References

- [SQLAlchemy Relationship Configuration](https://docs.sqlalchemy.org/en/20/orm/relationship_api.html#sqlalchemy.orm.relationship.params.foreign_keys)
- Issue #35: Organization billing contact caused ambiguous FK error
- Commit `1d9903a`: Fix specifying foreign_keys in Contact.organization relationship
