from .lockbox import FormGeometry
from .db import Form, FormField, FormFieldType

def form_geometry_compatible(geometry: FormGeometry, with_form: Form):
    if not with_form.sub_fields:
        return True

    for field in geometry.fields:
        if not any(x.index_on_page == field.index and x.kind == field.kind.value and x.expected_label_segment in field.title for x in with_form.sub_fields):
            return False

    return True


def create_default_fields_from_geometry(geometry: FormGeometry, into: Form):
    """
    Clears the fields of a form and replaces it with blank entries (specific to the field type)
    for all fields detected in a given form
    """

    into.sub_fields = []

    for field in geometry.fields:
        stripped_name = field.title
        if stripped_name.endswith(" *"):
            stripped_name = stripped_name[:-2]

        new_field = FormField(
            expected_label_segment=stripped_name,
            index_on_page=field.index,
            target_value={
                FormFieldType.DATE: "$today",
                FormFieldType.TEXT: "''",
                FormFieldType.LONG_TEXT: "''",
                FormFieldType.CHECKBOX: "0",
                FormFieldType.DROPDOWN: "0",
                FormFieldType.MULTIPLE_CHOICE: "0"
            }.get(field.kind, ''),
            kind=field.kind.value
        )

        into.sub_fields.append(new_field)
