import React from 'react';

import {Formik} from 'formik';
import * as yup from 'yup';

import Row from 'react-bootstrap/Row'
import Col from 'react-bootstrap/Col'
import Form from 'react-bootstrap/Form'
import Button from 'react-bootstrap/Button'

function SignupManualCode() {
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

	const doSubmit = (e) => {
	};

	return (<>
	<Row className="justify-content-center">
		<Col lg="6" xs="12">
			<h1>Sign Up</h1>
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
					code: ""
				}}
			>
			    {({
					handleSubmit,
					handleChange,
					values,
					errors
				}) => (
					<Form noValidate onSubmit={handleSubmit}>
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
						<Button type="submit">Next</Button>
					</Form>
				)}
			</Formik>
		</Col>
	</Row>
	</>);
}

export {SignupManualCode};
