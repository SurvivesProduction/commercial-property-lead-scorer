from datetime import date

import pytest
from pydantic import ValidationError

from leadscorer.normalize.schema import PermitRecord, PropertyRecord


def test_property_record_accepts_full_valid_record() -> None:
    prop = PropertyRecord(
        client_id="demo",
        source="example-source",
        parcel_id="P-001",
        address="100 Example Warehouse Way",
        city="Example City",
        county="Example County",
        state="MD",
        zip_code="21060",
        year_built=1975,
        year_renovated=None,
        square_footage=60000,
        property_use="Warehouse",
        owner_name="Example Logistics LLC",
        owner_mailing_address="PO Box 1, Example City, MD",
        raw_data={"id": "P-001"},
    )
    assert prop.parcel_id == "P-001"
    assert prop.square_footage == 60000


def test_property_record_allows_optional_fields_to_be_omitted() -> None:
    prop = PropertyRecord(
        client_id="demo",
        source="example-source",
        parcel_id="P-001",
        address="100 Example Warehouse Way",
    )
    assert prop.year_built is None
    assert prop.square_footage is None
    assert prop.raw_data == {}


def test_property_record_requires_core_fields() -> None:
    with pytest.raises(ValidationError):
        PropertyRecord(client_id="demo", source="example-source")


def test_permit_record_accepts_full_valid_record() -> None:
    permit = PermitRecord(
        client_id="demo",
        source="example-source",
        permit_number="PM-001",
        parcel_id="P-001",
        address="100 Example Warehouse Way",
        permit_type="Electrical",
        description="LED lighting retrofit",
        issued_date=date(2019, 6, 1),
        status="Finaled",
        raw_data={"id": "PM-001"},
    )
    assert permit.permit_number == "PM-001"
    assert permit.issued_date == date(2019, 6, 1)


def test_permit_record_allows_optional_fields_to_be_omitted() -> None:
    permit = PermitRecord(client_id="demo", source="example-source", permit_number="PM-001")
    assert permit.parcel_id is None
    assert permit.address is None
    assert permit.raw_data == {}


def test_permit_record_requires_core_fields() -> None:
    with pytest.raises(ValidationError):
        PermitRecord(client_id="demo", source="example-source")
