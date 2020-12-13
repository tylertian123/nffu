from fenetre.lockbox import FormGeometry
from fenetre.db import Form, FormField

def form_geometry_compatible(geometry: FormGeometry, with_form: Form):
    if not with_form.sub_fields:
        return True

    for field in geometry.fields:
        if not any(x.index_on_page == x.index and x.kind == field.kind and x.expected_label_segment in field.title for x in with_form.sub_fields):
            return False

    return True
