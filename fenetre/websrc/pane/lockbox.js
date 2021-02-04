import React from 'react';

import {Row, Col, Nav, FormCheck, Form, Button, Alert} from 'react-bootstrap';
import {LinkContainer} from 'react-router-bootstrap'
import {Route, Switch} from 'react-router'
import {ExtraUserInfoProvider} from '../common/userinfo';

import Cfg from './lockbox/cfg';
import Status from './lockbox/status';
import LockAdmin from './lockbox/admin';

import {AdminOnly} from '../common/userinfo';

function Lockbox() {
	return <Row>
		<Col md="4" lg="2" className="mb-3">
			<Nav variant="pills" className="flex-column">
				<LinkContainer to="/lockbox/cfg">
					<Nav.Link>Setup</Nav.Link>
				</LinkContainer>
				<LinkContainer to="/lockbox/status">
					<Nav.Link>Status</Nav.Link>
				</LinkContainer>
				<AdminOnly>
					<LinkContainer to="/lockbox/admin">
						<Nav.Link>Lockbox Admin</Nav.Link>
					</LinkContainer>
				</AdminOnly>
			</Nav>
		</Col>
		<Col md="8" lg="10">
			<ExtraUserInfoProvider>
				<Switch>
					<Route path="/lockbox/cfg">
						<Cfg />
					</Route>
					<Route path="/lockbox/status">
						<Status />
					</Route>
					<AdminOnly>
						<Route path="/lockbox/admin">
							<LockAdmin />
						</Route>
					</AdminOnly>
				</Switch>
			</ExtraUserInfoProvider>
		</Col>
	</Row>;
}

export default Lockbox;
