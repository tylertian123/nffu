import React from 'react';
import {useParams, Redirect} from 'react-router-dom';

import {Formik} from 'formik';
import * as yup from 'yup';

import Row from 'react-bootstrap/Row'
import Col from 'react-bootstrap/Col'
import Form from 'react-bootstrap/Form'
import Button from 'react-bootstrap/Button'
import Spinner from 'react-bootstrap/Spinner'

// fixes async in babel
import "regenerator-runtime/runtime";

function SignupBase(props) {
	const schema = yup.object({
		username: yup.string().required().min(6),
		password: yup.string().required().min(8),
		passwordConfirm: yup.string().test(
			'is-same',
			'passwords do not match',
			function(v) {
				return v === this.resolve(yup.ref('password'));
			}
		),
		code: yup.string().required().matches(/^[a-f0-9]{9}$/, 'invalid signup code format')
	});

	const [isDone, setDone] = React.useState(false);

	const doSubmit = async (values, {setStatus, setFieldError}) => {
		try {
			const response = await fetch('/api/v1/signup', {
				method: "POST",
				credentials: "same-origin",
				headers: {"Content-Type": "application/json"},
				body: JSON.stringify({
					username: values.username,
					password: values.password,
					token: values.code
				})
			});
			if (!response.ok) {
				const data = await response.json();

				if (data.error == "invalid request" && "extra" in data) {
					if ("username" in data.extra) setFieldError("username", data.extra["username"]);
					if ("password" in data.extra) setFieldError("password", data.extra["password"]);
					if ("token" in data.extra) setFieldError("code", data.extra["token"]);
				}
				else {
					setStatus(data.error);
				}
			}
			else {
				setDone(true);
			}
		}
		catch (err) {
			setStatus(err);
		}
	};

	return (<>
	{isDone ? (<Redirect to="/eula" />) : null}
	<Row className="justify-content-center">
		<Col lg="6" xs="12">
			<h1>Sign up</h1>
		</Col>
	</Row>
	<Row className="justify-content-center">
		<Col lg="6" xs="12">
			<Formik 
				validationSchema={schema}
				onSubmit={doSubmit}
				initialValues={{
					username: "",
					password: "",
					passwordConfirm: "",
					code: props.code === undefined ? "" : props.code
				}}
			>
			    {({
					handleSubmit,
					handleChange,
					values,
					errors,
					isSubmitting,
					status
				}) => (
					<Form noValidate onSubmit={handleSubmit}>
						{status ? (<p className="text-danger">{status}</p>) : null}
						<Form.Group>
							<Form.Control
								type="text"
								name="username"
								value={values.username}
								onChange={handleChange}
								isInvalid={!!errors.username}
								placeholder="Enter a username"
							/>
							<Form.Control.Feedback type="invalid">
								{errors.username}
							</Form.Control.Feedback>
						</Form.Group>
						<hr />
						<Form.Group>
							<Form.Control
								type="password"
								name="password"
								value={values.password}
								onChange={handleChange}
								isInvalid={!!errors.password}
								placeholder="Enter a password"
							/>
							<Form.Control.Feedback type="invalid">
								{errors.password}
							</Form.Control.Feedback>
						</Form.Group>
						<Form.Group>
							<Form.Control
								type="password"
								name="passwordConfirm"
								value={values.passwordConfirm}
								onChange={handleChange}
								isInvalid={!!errors.passwordConfirm}
								placeholder="Confirm your password"
							/>
							<Form.Control.Feedback type="invalid">
								{errors.passwordConfirm}
							</Form.Control.Feedback>
						</Form.Group>
						{props.code === undefined ? (<>
							<hr />
							<Form.Group>
								<Form.Control
									type="text"
									name="code"
									value={values.usercodename}
									onChange={handleChange}
									isInvalid={!!errors.code}
									placeholder="Enter your sign up code"
								/>
								<Form.Control.Feedback type="invalid">
									{errors.code}
								</Form.Control.Feedback>
							</Form.Group>
							<p>Confused? To sign up for <code>nffu</code> you need a sign up code. Try asking <code>latexbot</code> or <code>matbot</code> for one, or ask an administrator.</p>
						</>) : (
							<input type="hidden" value={props.code} name="code" />
						)}
						<Button type="submit" disabled={isSubmitting}>{isSubmitting ? (<Spinner className="mb-1" animation="border" size="sm" variant="light" />) : "Next"}</Button>
					</Form>
				)}
			</Formik>
		</Col>
	</Row>
	</>);
}

function SignupManualCode() {
	return <SignupBase />
}

function SignupProvidedCode() {
	const { code } = useParams();

	return <SignupBase code={code} />
}

export {SignupManualCode, SignupProvidedCode};
