import "./css/boot.scss";

// Main logged-in page.
// Login page (and all non-logged-in flow) is handled in login.js

import ReactDOM from 'react-dom';
import React from 'react';

import Container from 'react-bootstrap/Container'
import Row from 'react-bootstrap/Row'
import Col from 'react-bootstrap/Col'
import Form from 'react-bootstrap/Form'
import FormCheck from 'react-bootstrap/FormCheck'
import Button from 'react-bootstrap/Button'
import FlashBox from './common/flashbox'

function Login() {
	return (
		<div style={{
			minWidth: "100vw",
			width: "100vw",
			minHeight: "100vh",
			height: "100vh",
			display: "flex",
			flexDirection: "column",
			overflow: "auto"
		}}>
			<Container className="m-auto">
			<FlashBox />
			<Row className="justify-content-center">
				<Col lg="6" xs="12">
					<h1>Login</h1>
				</Col>
			</Row>
			<Row className="justify-content-center">
				<Col lg="6" xs="12">
					<Form method="post">
						<Form.Group>
							<Form.Control required name="username" type="text" placeholder="Enter your NFFU username" />
							<Form.Control required name="password" type="password" placeholder="Enter your NFFU password" />
						</Form.Group>
						<Form.Group>
							<FormCheck custom type="checkbox" label="Stay logged in?" name="remember_me" id="remember-me" />
						</Form.Group>
						<Button variant="success" type="submit">Go</Button>
					</Form>
					<hr />
					<p className="text-light">don't have an account? sign up <a href="/signup">here</a></p>
				</Col>
			</Row>
		</Container>
	</div>);
}

const mount = document.getElementById("mount");
ReactDOM.render(<Login />, mount);
