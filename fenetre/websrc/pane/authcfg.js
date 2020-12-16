import React from 'react';

import {Row, Col, Nav} from 'react-bootstrap';
import {LinkContainer} from 'react-router-bootstrap'
import {Route, Switch} from 'react-router'
import {AdminOnly} from '../common/userinfo';

import SignupProviders from './authcfg/signup_provider';
import Users from './authcfg/users';

function AuthCfg() {
	return <AdminOnly>
		<Row>
			<Col md="4" lg="2" className="mb-3">
				<Nav variant="pills" className="flex-column">
					<LinkContainer to="/authcfg/users">
						<Nav.Link>Users</Nav.Link>
					</LinkContainer>
					<LinkContainer to="/authcfg/signup_providers">
						<Nav.Link>Signup Providers</Nav.Link>
					</LinkContainer>
				</Nav>
			</Col>
			<Col md="8" lg="10">
				<Switch>
					<Route path="/authcfg/users">
						<Users />
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
