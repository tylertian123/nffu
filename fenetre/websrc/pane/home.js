import React from 'react';

import {UserInfoContext, AdminOnly, ExtraUserInfoContext, ExtraUserInfoProvider} from '../common/userinfo';
import {Alert, Button, Form, Row, Col, Spinner, Card} from 'react-bootstrap';
import {confirmationDialog} from '../common/confirms';
import {Formik} from 'formik';
import * as yup from 'yup';
import {Link} from 'react-router-dom';

import "regenerator-runtime/runtime";

function ConstantAlerts() {
	const extraUserInfo = React.useContext(ExtraUserInfoContext);

	if (extraUserInfo === null) return null;

	const alerts = [
		[extraUserInfo.lockbox_error, 
				<Alert variant="warning">There were problems when we last tried to fill in your attendance. You should probably see what they are <Link className="alert-link" to="/lockbox/status">here</Link></Alert>],
		[!extraUserInfo.has_lockbox_integration,
				<Alert variant="danger">Something went wrong while agreeing to the warnings and disclaimers and we don't have a place to store your credentials; please <a className="alert-link" href="/signup/eula">click here</a> to try again.</Alert>],
		[extraUserInfo.has_lockbox_integration && !extraUserInfo.lockbox_credentials_present,
				<Alert variant="info">You haven't setup your TDSB credentials yet, so we aren't filling in your attendance forms. Go <Link className="alert-link" to="/lockbox/cfg">here</Link> to set it up!</Alert>],
		[extraUserInfo.has_lockbox_integration && !extraUserInfo.lockbox_form_active,
				<Alert variant="info">You've disabled automatic attendance form filling. You can always turn it back on <Link className="alert-link" to="/lockbox/cfg">here</Link>!</Alert>],
		[extraUserInfo.unconfigured_courses_present && extraUserInfo.admin,
				<Alert variant="warning">There are courses with configuration pending approval and/or setup required. Go <Link className="alert-link" to="/forms/course">here</Link> to fix them!</Alert>]
	];

	if (alerts.reduce((a, [b, _]) => a || b, false)) {
		return <>
			<hr />
			{alerts.map(([a, val]) => a && val)}
		</>
	}
	else return null;
}

function UserDeleter() {
	const [isDeleting, setIsDeleting] = React.useState(false);

	const onDelete = async () => {
		if (!await confirmationDialog(<p>Are you <i>really</i> sure you want to delete your account? We'll delete all data we have on you and stop filling in your forms.</p>))
			return;

		// :(
		setIsDeleting(true);

		const result = await fetch("/api/v1/me", {
			credentials: "same-origin",
			method: "DELETE"
		});

		if (!result.ok) {
			// TODO: make me less awful
			alert("Failed to delete account");
			setSending(false);
			return;
		}

		// Send the user back to the main page.
		document.location.pathname = "/login";
	};

	return <Button disabled={isDeleting} variant="dark" onClick={onDelete}>Delete account</Button>
}

function UsernameChanger() {
	const userInfo = React.useContext(UserInfoContext);

	const schema = yup.object({
		username: yup.string().required().min(6).max(64).matches(/^\w+$/)
	});

	const [success, setSuccess] = React.useState(false);

	const doChangeUsername = async (values, {setStatus, setFieldError}) => {
		setSuccess(false);
		try {
			const response = await fetch('/api/v1/me', {
				method: "PATCH",
				credentials: "same-origin",
				headers: {"Content-Type": "application/json"},
				body: JSON.stringify({
					username: values.username
				})
			});
			if (!response.ok) {
				const data = await response.json();

				if (data.error == "invalid request" && "extra" in data) {
					if ("username" in data.extra) setFieldError("username", data.extra["username"]);
				}
				else {
					setStatus(data.error);
				}
			}
			else {
				setSuccess(true);
				setStatus(null);

				window.userinfo.name = values.username;
				userInfo.invalidate();
			}
		}
		catch (err) {
			setStatus(err);
		}
	};

	return <Formik validationSchema={schema}
		onSubmit={doChangeUsername}
		initialValues={{username: ''}}
	>
		{({
			handleSubmit,
			handleChange,
			handleBlur,
			values,
			errors,
			touched,
			isSubmitting,
			status
		}) => (
		<Form noValidate onSubmit={handleSubmit}>
			{success && <p className="text-success">Changed username!</p>}
			{status && (<p className="text-danger">{status}</p>)}
			<Form.Group>
				<Form.Label>New username</Form.Label>
				<Form.Control 
					name="username" 
					type="text" 
					onChange={handleChange}
					onBlur={handleBlur}
					isInvalid={!!errors.username && touched.username}
					value={values.username}
				/>
				<Form.Control.Feedback type="invalid">
					{errors.username}
				</Form.Control.Feedback>
			</Form.Group>

			<Button type="submit" disabled={isSubmitting}>{isSubmitting ? (<Spinner className="mb-1" animation="border" size="sm" variant="light" />) : "Update username"}</Button>
		</Form>)}
	</Formik>;
}

function PasswordChanger() {
	const schema = yup.object({
		oldPassword: yup.string().required(),
		password: yup.string().required().min(8),
		passwordConfirm: yup.string().test(
			'is-same',
			'passwords do not match',
			function(v) {
				return v === this.resolve(yup.ref('password'));
			}
		)
	});

	const [success, setSuccess] = React.useState(false);

	const doChangePassword = async (values, {setFieldError, setStatus}) => {
		setSuccess(false);
		try {
			const response = await fetch('/api/v1/me', {
				method: "PATCH",
				credentials: "same-origin",
				headers: {"Content-Type": "application/json"},
				body: JSON.stringify({
					password: values.password,
					current_password: values.oldPassword
				})
			});
			if (!response.ok) {
				const data = await response.json();

				if (data.error == "invalid request" && "extra" in data) {
					if ("password" in data.extra) setFieldError("password", data.extra["password"]);
				}
				else {
					setStatus(data.error);
				}
			}
			else {
				setSuccess(true);
				setStatus(null);
			}
		}
		catch (err) {
			setStatus(err);
		}
	};

	return <Formik validationSchema={schema}
				onSubmit={doChangePassword}
				initialValues={{
					password: '', passwordConfirm: '', oldPassword: ''
				}}
			>
			{({
				handleSubmit,
				handleChange,
				handleBlur,
				values,
				errors,
				touched,
				isSubmitting,
				status
			}) => (
			<Form noValidate onSubmit={handleSubmit}>
					{success && <p className="text-success">Changed password!</p>}
					{status && (<p className="text-danger">{status}</p>)}
					<Form.Group>
						<Form.Label>Old password</Form.Label>
						<Form.Control 
							name="oldPassword" 
							type="password" 
							onChange={handleChange}
							onBlur={handleBlur}
							isInvalid={!!errors.oldPassword && touched.oldPassword}
							value={values.oldPassword}
						/>
						<Form.Control.Feedback type="invalid">
							{errors.oldPassword}
						</Form.Control.Feedback>
					</Form.Group>

					<Form.Group>
						<Form.Label>New password</Form.Label>
						<Form.Control 
							name="password" 
							type="password" 
							onChange={handleChange}
							onBlur={handleBlur}
							isInvalid={!!errors.password && touched.password}
							value={values.password}
						/>
						<Form.Control.Feedback type="invalid">
							{errors.password}
						</Form.Control.Feedback>
					</Form.Group>

					<Form.Group>
						<Form.Label>Confirm new password</Form.Label>
						<Form.Control 
							name="passwordConfirm" 
							type="password" 
							onChange={handleChange}
							onBlur={handleBlur}
							isInvalid={!!errors.passwordConfirm && touched.passwordConfirm}
							value={values.passwordConfirm}
						/>
						<Form.Control.Feedback type="invalid">
							{errors.passwordConfirm}
						</Form.Control.Feedback>
					</Form.Group>

					<Button type="submit" disabled={isSubmitting}>{isSubmitting ? (<Spinner className="mb-1" animation="border" size="sm" variant="light" />) : "Update password"}</Button>
			</Form>)}
	</Formik>
}

function Home() {
	const userinfo = React.useContext(UserInfoContext);

	return (<>
		<h1>Hello, <b>{userinfo.name}</b></h1>
		<AdminOnly>
			<p>You are logged in with <i>administrative</i> privileges.</p>
		</AdminOnly>
		<ExtraUserInfoProvider>
			<ConstantAlerts />
		</ExtraUserInfoProvider>
		<h2>Account settings</h2>
		<hr />
		<Row>
			<Col md className="mb-3">
				<h3>Change password</h3>
				<PasswordChanger />
			</Col>
			<Col md className="mb-3">
				<h3>Change username</h3>
				<UsernameChanger />
			</Col>
			<Col md>
				<Card bg="danger">
					<Card.Header><h3>Danger zone</h3></Card.Header>
					<Card.Body>
						<UserDeleter />
					</Card.Body>
				</Card>
			</Col>
		</Row>
		<hr />
		<p><code>nffu</code> version 0.1.11</p>
	</>);
}

export default Home;
