import React from 'react';

import {Row, Col, FormCheck, Form, Button, Alert, Spinner, ListGroup} from 'react-bootstrap';
import {ExtraUserInfoContext} from '../../common/userinfo';
import {useFormik} from 'formik';
import * as yup from 'yup';
import {Link, Redirect, Switch, Route, useParams} from 'react-router-dom';
import useBackoffEffect from '../../common/pendprovider';

import {BsCheckAll, BsCheck, BsExclamationCircle, BsArrowRight, BsArrowLeft, BsArrowClockwise} from 'react-icons/bs';

import "regenerator-runtime/runtime";

function FormListEntry(props) {
	const {form} = props;

	return <ListGroup.Item>
		<div className="text-dark d-flex w-100 justify-content-between">
			<h3 className="mb-0">{form.name}</h3>
			<Form inline className="align-self-middle">
				<FormCheck id={"def-switch-" + form.id} onChange={(e) => props.onSetDefault(form.id, e.target.value)} checked={form.is_default} type="switch" custom label="Default" />
			</Form>
		</div>
		<div className="d-flex mt-2 w-100 justify-content-between align-items-end">
			<ul className="mb-0">
				<li>Used by <span className="text-info">{form.used_by}</span> courses</li>
				{form.representative_thumbnail || <li><i>no thumbnail set</i></li>}
			</ul>
			<Button>Edit <BsArrowRight /></Button>
		</div>
	</ListGroup.Item>
}

function FormList() {
	const [forms, setForms] = React.useState(null);

	React.useEffect(() => {
		(async () => {
			const resp = await fetch("/api/v1/form");
			if (resp.ok) {
				const dat = await resp.json();

				setForms(dat.forms);
			}
		})();
	}, []);

	if (forms === null) {
		return <Alert className="d-flex align-items-center" variant="secondary"><Spinner className="mr-2" animation="border" /> loading...</Alert>;
	}

	return <ListGroup className="bg-light">
		{forms.map((x) => <FormListEntry key={x.id} form={x} />)}
	</ListGroup>
}

export default FormList;
