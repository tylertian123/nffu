import React from 'react';
import reactModal from '@prezly/react-promise-modal';

import {Row, Col, FormCheck, Form, Button, Alert, Spinner, ListGroup, Modal} from 'react-bootstrap';
import {ExtraUserInfoContext} from '../../common/userinfo';
import {Formik} from 'formik';
import {LinkContainer} from 'react-router-bootstrap';
import * as yup from 'yup';
import {Link, Redirect, Switch, Route, useParams} from 'react-router-dom';
import useBackoffEffect from '../../common/pendprovider';

import {BsCheckAll, BsCheck, BsExclamationCircle, BsArrowRight, BsArrowLeft, BsArrowClockwise, BsPlus} from 'react-icons/bs';

import "regenerator-runtime/runtime";

// awaitable
function NewFormDialog() {
	const schema = yup.object({
		name: yup.string().required(),
		initialize_from: yup.string().matches(/^(?:https?:\/\/)?docs.google.com\/forms(?:\/u\/\d+)?\/d\/e\/([A-Za-z0-9-_]+)\/viewform/, "url should be a google form url"),
		use_fields_from_url: yup.bool()
	});

	function sleep(ms) {
	  return new Promise(resolve => setTimeout(resolve, ms));
	}

	return reactModal(({show, onSubmit, onDismiss}) => (
		<Modal centered show={show} onHide={onDismiss}>
			<Modal.Header>
				<Modal.Title>
					New form
				</Modal.Title>
			</Modal.Header>

			<Formik 
				initialValues={{name: '', initialize_from: '', use_fields_from_url: true}}
				validationSchema={schema}
				onSubmit={async (values, {setStatus, setFieldError}) => {
					let tries = 0;
					while (tries < 10) {
						try {
							const resp = await fetch("/api/v1/form", {
								method: "POST",
								headers: {"Content-Type": "application/json"},
								body: JSON.stringify(values)
							});
							const data = await resp.json();

							if (!resp.ok) {
								if (data.error == "invalid request" && "extra" in data) {
									if ("name" in data.extra) setFieldError("name", data.extra["name"]);
									if ("initialize_from" in data.extra) setFieldError("initialize_from", data.extra["initialize_from"]);
									if ("use_fields_from_url" in data.extra) setFieldError("use_fields_from_url", data.extra["use_fields_from_url"]);
								}
								else {
									setStatus(data.error);
								}
								return;
							}
							else if (data.status == "ok") {
								onSubmit(data.form);
								return;
							}
						}
						catch (err) {
							setStatus(err);
							return;
						}

						// Pending, go for another loop
						await sleep(2800);
						++tries;
					}
					setStatus("Timed out");
				}}
			>
				{(formik) => 
				<Form noValidate onSubmit={formik.handleSubmit}>
					<Modal.Body>
						{formik.status && <p className="text-danger">{formik.status}</p>}
						<Form.Group>
							<Form.Label>Name</Form.Label>
							<Form.Control type="text" name="name" isInvalid={!!formik.errors.name} 
								placeholder="User-visible form style name"
								{...formik.getFieldProps("name")} />
							<Form.Control.Feedback type="invalid">{formik.errors.name}</Form.Control.Feedback>
						</Form.Group>

						<hr />

						<h3>Auto-init</h3>
						<Form.Group>
							<Form.Label>Setup from URL</Form.Label>
							<Form.Control type="text" name="initialize_from" isInvalid={!!formik.errors.initialize_from} 
								{...formik.getFieldProps("initialize_from")} />
							<Form.Control.Feedback type="invalid">{formik.errors.initialize_from}</Form.Control.Feedback>
						</Form.Group>
						<Form.Group>
							<Form.Check type="checkbox" name="use_fields_from_url" checked={formik.values.use_fields_from_url} onChange={formik.onChange} label="Load default fields from geometry?" />
						</Form.Group>
					</Modal.Body>

					<Modal.Footer>
						<Button type="submit" disabled={formik.isSubmitting}>{formik.isSubmitting ? (<Spinner className="mb-1" animation="border" size="sm" variant="light" />) : "Create"}</Button>
					</Modal.Footer>
				</Form>}
			</Formik>
		</Modal>
	));
}

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
				{!!form.representative_thumbnail || <li><i>no thumbnail set</i></li>}
			</ul>
			<LinkContainer to={"/forms/form/" + form.id}>
				<Button>Edit <BsArrowRight /></Button>
			</LinkContainer>
		</div>
	</ListGroup.Item>
}

function FormList() {
	const [forms, setForms] = React.useState(null);
	const [redirecting, setRedirecting] = React.useState('');

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

	return <>
		<ListGroup className="bg-light">
			{forms.map((x) => <FormListEntry key={x.id} form={x} />)}
		</ListGroup>
		<Button className="mt-2" variant="success" onClick={async () => {
			const new_url = await NewFormDialog();
			if (!new_url) return;
			setRedirecting("/forms/form/" + new_url.id);
		}}><BsPlus /> New</Button>
		{redirecting && <Redirect to={redirecting} />}
	</>;
}

export default FormList;
