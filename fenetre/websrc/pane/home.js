import React from 'react';

import {UserInfoContext, AdminOnly} from '../common/userinfo';
import {Alert, Button, Form, Row, Col, Spinner} from 'react-bootstrap';
import {Formik} from 'formik';
import * as yup from 'yup';

import "regenerator-runtime/runtime";

function ConstantAlerts(props) {
	const extraUserInfo = props.extraUserInfo;

	const alerts = [
		[extraUserInfo.lockbox_error, 
				<Alert variant="warning">There were problems when we last tried to fill in your attendance. You should probably see what they are <a>hereTODO</a></Alert>],
		[!extraUserInfo.has_lockbox_integration,
				<Alert variant="danger">Something went wrong while agreeing to the warnings and disclaimers and we don't have a place to store your credentials; please <a href="/signup/eula">click here</a> to try again.</Alert>],
		[/*extraUserInfo.has_lockbox_integration &&*/ !extraUserInfo.lockbox_credentials_present,
				<Alert variant="info">You haven't setup your TDSB credentials yet, so we aren't filling in your attendance forms. Go <a>here</a> to set it up!</Alert>],
		[/*extraUserInfo.has_lockbox_integration &&*/ !extraUserInfo.lockbox_form_active /*&& extraUserInfo.lockbox_credentials_present*/,
				<Alert variant="info">You've disabled automatic attendance form filling. You can always turn it back on <a>here</a>!</Alert>]
	];

	if (alerts.reduce((a, [b, _]) => a || b, false)) {
		return <>
			<hr />
			{alerts.map(([a, val]) => a && val)}
		</>
	}
	else return null;
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

	const [extraUserInfo, setEUI] = React.useState(null);

	React.useEffect(() => {
		(async ()=>{
			const response = await fetch("/api/v1/me");
			setEUI(await response.json());
		})();
	}, []);

	return (<>
		<h1>Hello, <b>{userinfo.name}</b></h1>
		<AdminOnly>
			<p>You are logged in with <i>administrative</i> privileges.</p>
		</AdminOnly>
		{extraUserInfo !== null && <ConstantAlerts extraUserInfo={extraUserInfo}/>}
		<h2>Account settings</h2>
		<hr />
		<Row>
			<Col md>
				<h3>Change password</h3>
				<PasswordChanger />
			</Col>
			<Col md>
				<h3>Change username</h3>
			</Col>
			<Col md>
				<h3 className="text-danger">Delete account</h3>
			</Col>
		</Row>
	</>);
}

export default Home;
