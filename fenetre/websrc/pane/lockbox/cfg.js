import React from 'react';

import {Row, Col, FormCheck, Form, Button, Alert, Spinner} from 'react-bootstrap';
import {ExtraUserInfoContext} from '../../common/userinfo';
import {useFormik} from 'formik';
import * as yup from 'yup';
import {Link} from 'react-router-dom';
import useBackoffEffect from '../../common/pendprovider';

import "regenerator-runtime/runtime";

function CredentialChangerAlerts() {
	const eui = React.useContext(ExtraUserInfoContext);
	if (eui === null) return null;

	return eui.lockbox_credentials_present ? 
		<Alert variant="success">You've already filled in your TDSB credentials; you only need to use this area if you changed your password.</Alert> :
		<Alert variant="warning">You haven't filled out your TDSB credentials yet; to start filling in forms you need to set them here.</Alert>;
}

function CredentialChanger() {
	const schema = yup.object({
		username: yup.string().required().matches(/\d{5,9}/, "username should be 5 to 9 digits"),
		password: yup.string().required()
	});

	const eui = React.useContext(ExtraUserInfoContext);

	const [done, setDone] = React.useState(false);

	const doSubmit = async (values, {setStatus, setFieldError}) => {
		if (done) setDone(false);

		try {
			const response = await fetch('/api/v1/me/lockbox', {
				method: "PATCH",
				headers: {"Content-Type": "application/json"},
				body: JSON.stringify({
					username: values.username,
					password: values.password
				})
			});
			if (!response.ok) {
				const data = await response.json();

				if (data.error == "invalid request" && "extra" in data) {
					if ("username" in data.extra) setFieldError("username", data.extra["username"]);
					if ("password" in data.extra) setFieldError("password", data.extra["password"]);
				}
				else {
					setStatus(data.error);
				}
			}
			else {
				setDone(true);
				eui.invalidate();
			}
		}
		catch (err) {
			setStatus(err);
		}
	};

	const formik = useFormik({
		initialValues: {username: '', password: ''},
		onSubmit: doSubmit,
		validationSchema: schema
	});

	return <>
		<CredentialChangerAlerts />
		<Form noValidate onSubmit={formik.handleSubmit}>
			{done && <p className="text-success">Saved!</p>}
			<Form.Group>
				<Form.Label>TDSB Username</Form.Label>
				<Form.Control type="text" name="username" isInvalid={!!formik.errors.username && formik.touched.username} {...formik.getFieldProps('username')} />
				<Form.Control.Feedback type="invalid">{formik.errors.username}</Form.Control.Feedback>
			</Form.Group>

			<Form.Group>
				<Form.Label>TDSB Password</Form.Label>
				<Form.Control type="password" name="password" isInvalid={!!formik.errors.password && formik.touched.password} {...formik.getFieldProps('password')} />
				<Form.Control.Feedback type="invalid">{formik.errors.password}</Form.Control.Feedback>
			</Form.Group>

			<Button type="submit" disabled={formik.isSubmitting || eui === null}>{formik.isSubmitting ? (<Spinner className="mb-1" animation="border" size="sm" variant="light" />) : "Update credentials"}</Button>
		</Form>
	</>;
};

function Enabler() {
	const [working, setWorking] = React.useState(false);
	const eui = React.useContext(ExtraUserInfoContext);
	const [privateEnabled, setPrivateEnabled] = React.useState(eui.lockbox_form_active);
	const [status, setStatus] = React.useState('');

	const update = async (e) => {
		console.log("heloo");
		const oldValue = privateEnabled;
		const nv = e.target.checked;

		setPrivateEnabled(nv);
		setWorking(true);

		try {
			const response = await fetch('/api/v1/me/lockbox', {
				method: "PATCH",
				headers: {"Content-Type": "application/json"},
				body: JSON.stringify({
					active: nv
				})
			});

			if (!response.ok) {
				const data = await response.json();
				setPrivateEnabled(oldValue);
				setStatus(data.error);
			}
		}
		catch (err) {
			setStatus(err);
		}
		finally {
			setWorking(false);
		}
	};

	return <>
		<FormCheck onClick={update} checked={privateEnabled} disabled={working || eui === null} custom id="form-enable" type="switch" label="Enable form-filling" />
		{working && <Spinner size="sm" animation="border" />}
	</>;
};

function CourseDetector() {
	const [courses, setCourses] = React.useState(null);
	const [pending, setPending] = React.useState(null);

	useBackoffEffect(async () => {
		const response = await fetch("/api/v1/me/lockbox/courses");
		const data = await response.json();
		const pending = data.status == "pending";

		setPending(pending);

		if (pending) return true;
		setCourses(data.courses);
		return false;
	}, []);

	if (courses === null) {
		if (pending !== null && pending) {
			return <Alert className="d-flex align-items-center" variant="info"><Spinner className="mr-2" animation="border" /> We're still grabbing your courses from TDSB Connects; please wait a bit.</Alert>;
		}
		else {
			return <Alert className="d-flex align-items-center" variant="secondary"><Spinner className="mr-2" animation="border" /> loading...</Alert>;
		}
	}

	return null;
}

function Cfg() {
	const eui = React.useContext(ExtraUserInfoContext);

	if (eui !== null && !eui.has_lockbox_integration) return null;

	return (<div>
		<Row>
			<Col sm className="mb-3">
				<h2>Change credentials</h2>
				<CredentialChanger />
			</Col>
			<Col sm>
				<h2>Form-filling configuration</h2>
				{eui !== null &&
					<Enabler />}
			</Col>
		</Row>
		{eui !== null && eui.lockbox_credentials_present && (<Row>
			<Col>
				<h2>Detected courses</h2>
				<CourseDetector />
			</Col>
		</Row>)}
	</div>);
};

export default Cfg;
