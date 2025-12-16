"""Tests for organizations API endpoints and schemas."""

from datetime import date, datetime
from uuid import uuid4

from app.schemas.organization import (
    BillingContactSummary,
    ContactSummaryForOrg,
    OrganizationCreate,
    OrganizationDetail,
    OrganizationDetailWithRelations,
    OrganizationResponse,
    OrganizationUpdate,
    ProjectSummaryForOrg,
)


class TestOrganizationSchemas:
    """Tests for Organization Pydantic schemas."""

    def test_organization_response_schema(self):
        """OrganizationResponse should validate basic organization data."""
        org_id = uuid4()
        now = datetime.now()

        data = OrganizationResponse(
            id=org_id,
            name="Test Organization",
            aliases=["Test Org", "TO"],
            created_at=now,
            updated_at=now,
        )

        assert data.id == org_id
        assert data.name == "Test Organization"
        assert data.aliases == ["Test Org", "TO"]

    def test_organization_detail_has_project_count(self):
        """OrganizationDetail should include project_count."""
        org_id = uuid4()
        now = datetime.now()

        data = OrganizationDetail(
            id=org_id,
            name="Test Organization",
            aliases=None,
            created_at=now,
            updated_at=now,
            project_count=5,
        )

        assert data.project_count == 5

    def test_organization_detail_with_relations_has_projects_and_contacts(self):
        """OrganizationDetailWithRelations should include projects and contacts arrays."""
        org_id = uuid4()
        project_id = uuid4()
        contact_id = uuid4()
        now = datetime.now()
        today = date.today()

        project_summary = ProjectSummaryForOrg(
            id=project_id,
            name="Test Project",
            status="active",
            start_date=today,
            end_date=None,
        )

        contact_summary = ContactSummaryForOrg(
            id=contact_id,
            name="John Doe",
            email="john@example.com",
            role_title="Manager",
        )

        data = OrganizationDetailWithRelations(
            id=org_id,
            name="Test Organization",
            aliases=["Test Org"],
            created_at=now,
            updated_at=now,
            project_count=1,
            projects=[project_summary],
            contacts=[contact_summary],
        )

        assert len(data.projects) == 1
        assert len(data.contacts) == 1
        assert data.projects[0].name == "Test Project"
        assert data.contacts[0].email == "john@example.com"


class TestProjectSummaryForOrg:
    """Tests for ProjectSummaryForOrg schema."""

    def test_project_summary_requires_start_date(self):
        """ProjectSummaryForOrg should require start_date."""
        project_id = uuid4()
        today = date.today()

        data = ProjectSummaryForOrg(
            id=project_id,
            name="Test Project",
            status="active",
            start_date=today,
        )

        assert data.start_date == today
        assert data.end_date is None

    def test_project_summary_with_end_date(self):
        """ProjectSummaryForOrg should allow optional end_date."""
        project_id = uuid4()
        start = date(2024, 1, 1)
        end = date(2024, 12, 31)

        data = ProjectSummaryForOrg(
            id=project_id,
            name="Test Project",
            status="completed",
            start_date=start,
            end_date=end,
        )

        assert data.end_date == end

    def test_project_summary_status_is_string(self):
        """ProjectSummaryForOrg status should be a string."""
        project_id = uuid4()

        data = ProjectSummaryForOrg(
            id=project_id,
            name="Test Project",
            status="approved",
            start_date=date.today(),
        )

        assert isinstance(data.status, str)
        assert data.status == "approved"


class TestContactSummaryForOrg:
    """Tests for ContactSummaryForOrg schema."""

    def test_contact_summary_required_fields(self):
        """ContactSummaryForOrg should require id, name, and email."""
        contact_id = uuid4()

        data = ContactSummaryForOrg(
            id=contact_id,
            name="Jane Doe",
            email="jane@example.com",
        )

        assert data.id == contact_id
        assert data.name == "Jane Doe"
        assert data.email == "jane@example.com"
        assert data.role_title is None

    def test_contact_summary_with_role(self):
        """ContactSummaryForOrg should allow optional role_title."""
        contact_id = uuid4()

        data = ContactSummaryForOrg(
            id=contact_id,
            name="Jane Doe",
            email="jane@example.com",
            role_title="CEO",
        )

        assert data.role_title == "CEO"


class TestOrganizationDetailWithRelationsDefaults:
    """Tests for default values in OrganizationDetailWithRelations."""

    def test_empty_projects_list_default(self):
        """Projects should default to empty list."""
        org_id = uuid4()
        now = datetime.now()

        data = OrganizationDetailWithRelations(
            id=org_id,
            name="Empty Org",
            aliases=None,
            created_at=now,
            updated_at=now,
            project_count=0,
        )

        assert data.projects == []
        assert data.contacts == []

    def test_multiple_projects_and_contacts(self):
        """Should support multiple projects and contacts."""
        org_id = uuid4()
        now = datetime.now()
        today = date.today()

        projects = [
            ProjectSummaryForOrg(
                id=uuid4(),
                name=f"Project {i}",
                status="active",
                start_date=today,
            )
            for i in range(5)
        ]

        contacts = [
            ContactSummaryForOrg(
                id=uuid4(),
                name=f"Contact {i}",
                email=f"contact{i}@example.com",
            )
            for i in range(3)
        ]

        data = OrganizationDetailWithRelations(
            id=org_id,
            name="Test Org",
            aliases=None,
            created_at=now,
            updated_at=now,
            project_count=5,
            projects=projects,
            contacts=contacts,
        )

        assert len(data.projects) == 5
        assert len(data.contacts) == 3


class TestOrganizationModelRelationships:
    """Tests for Organization model relationship definitions."""

    def test_organization_has_projects_relationship(self):
        """Organization model should have projects relationship."""
        from app.models import Organization

        assert hasattr(Organization, "projects")

    def test_organization_has_contacts_relationship(self):
        """Organization model should have contacts relationship."""
        from app.models import Organization

        assert hasattr(Organization, "contacts")


class TestOrganizationWithNewFields:
    """Tests for Organization schemas with new fields."""

    def test_organization_response_with_address(self):
        """OrganizationResponse should include address fields."""
        org_id = uuid4()
        now = datetime.now()

        data = OrganizationResponse(
            id=org_id,
            name="Test Organization",
            aliases=None,
            billing_contact_id=None,
            address_street="123 Main St",
            address_city="Boston",
            address_state="MA",
            address_zip="02101",
            address_country="USA",
            inventory_url="https://inventory.example.com/123",
            notes="Test notes",
            created_at=now,
            updated_at=now,
        )

        assert data.address_street == "123 Main St"
        assert data.address_city == "Boston"
        assert data.address_state == "MA"
        assert data.address_zip == "02101"
        assert data.address_country == "USA"
        assert data.inventory_url == "https://inventory.example.com/123"
        assert data.notes == "Test notes"

    def test_organization_all_new_fields_optional(self):
        """All new fields should be optional."""
        org_id = uuid4()
        now = datetime.now()

        # Should not raise with minimal fields
        data = OrganizationResponse(
            id=org_id,
            name="Minimal Org",
            aliases=None,
            created_at=now,
            updated_at=now,
        )

        assert data.billing_contact_id is None
        assert data.address_street is None
        assert data.notes is None

    def test_organization_create_with_new_fields(self):
        """OrganizationCreate should accept new fields."""
        data = OrganizationCreate(
            name="New Org",
            address_city="New York",
            notes="Created with notes",
        )

        assert data.name == "New Org"
        assert data.address_city == "New York"
        assert data.notes == "Created with notes"

    def test_organization_update_partial(self):
        """OrganizationUpdate should support partial updates."""
        data = OrganizationUpdate(notes="Updated notes only")
        dump = data.model_dump(exclude_unset=True)

        assert dump == {"notes": "Updated notes only"}
        assert "name" not in dump


class TestBillingContactSummary:
    """Tests for BillingContactSummary schema."""

    def test_billing_contact_summary_required_fields(self):
        """BillingContactSummary should require id, name, email."""
        contact_id = uuid4()
        data = BillingContactSummary(
            id=contact_id,
            name="Billing Person",
            email="billing@example.com",
        )

        assert data.id == contact_id
        assert data.name == "Billing Person"
        assert data.email == "billing@example.com"
        assert data.role_title is None

    def test_billing_contact_with_role(self):
        """BillingContactSummary should allow optional role_title."""
        data = BillingContactSummary(
            id=uuid4(),
            name="CFO",
            email="cfo@example.com",
            role_title="Chief Financial Officer",
        )

        assert data.role_title == "Chief Financial Officer"


class TestOrganizationDetailWithBillingContact:
    """Tests for OrganizationDetailWithRelations with billing contact."""

    def test_detail_with_billing_contact(self):
        """OrganizationDetailWithRelations should include billing_contact."""
        org_id = uuid4()
        billing_id = uuid4()
        now = datetime.now()

        billing = BillingContactSummary(
            id=billing_id,
            name="Billing Contact",
            email="billing@example.com",
        )

        data = OrganizationDetailWithRelations(
            id=org_id,
            name="Test Org",
            aliases=None,
            billing_contact_id=billing_id,
            address_city="Boston",
            created_at=now,
            updated_at=now,
            project_count=0,
            billing_contact=billing,
        )

        assert data.billing_contact is not None
        assert data.billing_contact.name == "Billing Contact"

    def test_detail_without_billing_contact(self):
        """OrganizationDetailWithRelations should work without billing_contact."""
        org_id = uuid4()
        now = datetime.now()

        data = OrganizationDetailWithRelations(
            id=org_id,
            name="Test Org",
            aliases=None,
            created_at=now,
            updated_at=now,
            project_count=0,
        )

        assert data.billing_contact is None


class TestOrganizationModelNewFields:
    """Tests for Organization model new field definitions."""

    def test_organization_has_billing_contact_relationship(self):
        """Organization model should have billing_contact relationship."""
        from app.models import Organization

        assert hasattr(Organization, "billing_contact")

    def test_organization_has_new_columns(self):
        """Organization model should have new columns."""
        from app.models import Organization

        columns = [c.name for c in Organization.__table__.columns]
        assert "billing_contact_id" in columns
        assert "address_street" in columns
        assert "address_city" in columns
        assert "address_state" in columns
        assert "address_zip" in columns
        assert "address_country" in columns
        assert "inventory_url" in columns
        assert "notes" in columns
