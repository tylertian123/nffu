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
				<FormCheck id={"def-switch-" + form.id} checked={form.is_default} type="switch" custom label="Default" />
			</Form>
		</div>
		<div className="d-flex mt-2 w-100 justify-content-between align-items-end">
			<ul>
				<li>Used by <span className="text-info">{form.used_by}</span> courses</li>
			</ul>
			<Button>Edit <BsArrowRight /></Button>
		</div>
	</ListGroup.Item>
}

function FormList() {
	return <ListGroup className="bg-light">
		<FormListEntry form={{
			name: "test form",
			id: "aaaaaaa",
			is_default: true,
			used_by: 4
		}} />
		<FormListEntry form={{
			name: "test form 2",
			id: "aaaaaaa",
			is_default: false,
			used_by: 3
		}} />
	</ListGroup>
}

export default FormList;
