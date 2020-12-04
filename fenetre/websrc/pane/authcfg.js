import React from 'react';

import {Row, Col, Nav} from 'react-bootstrap';
import {LinkContainer} from 'react-router-bootstrap'
import {Route, Switch} from 'react-router'
import {AdminOnly} from '../common/userinfo';

import SignupProviders from './authcfg/signup_provider';

import "regenerator-runtime/runtime";

function AuthCfg() {
	return <AdminOnly>
		<Row>
			<Col xs="5" md="4" lg="3">
				<Nav variant="pills" className="flex-column">
					<LinkContainer to="/authcfg/users">
						<Nav.Link>Users</Nav.Link>
					</LinkContainer>
					<LinkContainer to="/authcfg/signup_providers">
						<Nav.Link>Signup Providers</Nav.Link>
					</LinkContainer>
				</Nav>
			</Col>
			<Col xs="7" md="8" lg="9">
				<Switch>
					<Route path="/authcfg/users">
						<p>I exist</p>
					</Route>
					<Route path="/authcfg/signup_providers">
						<SignupProviders />
					</Route>
				</Switch>
			</Col>
		</Row>
	</AdminOnly>;
}

export default AuthCfg;
