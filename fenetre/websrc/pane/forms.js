import React from 'react';

import {Row, Col, Nav, FormCheck, Form, Button, Alert} from 'react-bootstrap';
import {LinkContainer} from 'react-router-bootstrap'
import {Route, Switch} from 'react-router'
import {ExtraUserInfoProvider} from '../common/userinfo';

import FormList from './forms/formlist';
import FormEditor from './forms/formeditor';
import AdmCourseList from './forms/courselist';

function Forms() {
	return <Row>
		<Col md="4" lg="2" className="mb-3">
			<Nav variant="pills" className="flex-column">
				<LinkContainer to="/forms/form">
					<Nav.Link>Forms</Nav.Link>
				</LinkContainer>
				<LinkContainer to="/forms/course">
					<Nav.Link>Courses</Nav.Link>
				</LinkContainer>
			</Nav>
		</Col>
		<Col md="8" lg="10">
			<ExtraUserInfoProvider>
				<Switch>
					<Route path="/forms/form/:idx">
						<FormEditor />
					</Route>
					<Route path="/forms/form">
						<FormList />
					</Route>
					<Route path="/forms/course">
						<AdmCourseList />
					</Route>
				</Switch>
			</ExtraUserInfoProvider>
		</Col>
	</Row>;
}

export default Forms;
