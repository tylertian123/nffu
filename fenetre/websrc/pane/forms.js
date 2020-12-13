import React from 'react';

import {Row, Col, Nav, FormCheck, Form, Button, Alert} from 'react-bootstrap';
import {LinkContainer} from 'react-router-bootstrap'
import {Route, Switch} from 'react-router'
import {ExtraUserInfoProvider} from '../common/userinfo';
import FormList from './forms/formlist';

function Forms() {
	return <Row>
		<Col sm md="4" lg="2" className="mb-3">
			<Nav variant="pills" className="flex-column">
				<LinkContainer to="/forms/form">
					<Nav.Link>Forms</Nav.Link>
				</LinkContainer>
			</Nav>
		</Col>
		<Col sm md="8" lg="10">
			<ExtraUserInfoProvider>
				<Switch>
					<Route path="/forms/form">
						<FormList />
					</Route>
				</Switch>
			</ExtraUserInfoProvider>
		</Col>
	</Row>;
}

export default Forms;
