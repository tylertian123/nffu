import React from 'react';

import {Row, Col, Nav, FormCheck, Form, Button, Alert} from 'react-bootstrap';
import {LinkContainer} from 'react-router-bootstrap'
import {Route, Switch} from 'react-router'

import FormList from './forms/formlist';
import FormEditor from './forms/formeditor';
import AdmCourseList from './forms/courselist';
import CourseEditor from './forms/courseedit';
import {CourseTester, CourseTestViewer} from './forms/coursetester';

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
			<Switch>
				<Route path="/forms/form/:idx">
					<FormEditor />
				</Route>
				<Route path="/forms/form">
					<FormList />
				</Route>
				<Route path="/forms/course/:idx/test/:testidx">
					<CourseTestViewer />
				</Route>
				<Route path="/forms/course/:idx/test">
					<CourseTester />
				</Route>
				<Route path="/forms/course/:idx">
					<CourseEditor />
				</Route>
				<Route path="/forms/course">
					<AdmCourseList />
				</Route>
			</Switch>
		</Col>
	</Row>;
}

export default Forms;
