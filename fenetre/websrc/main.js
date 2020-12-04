import "./css/boot.scss";

// Main logged-in page.
// Login page (and all non-logged-in flow) is handled in login.js

import ReactDOM from 'react-dom';
import React from 'react';

import {BrowserRouter as Router, Route, Switch} from 'react-router-dom'
import {LinkContainer} from 'react-router-bootstrap'
import Navbar from 'react-bootstrap/Navbar'
import Nav from 'react-bootstrap/Nav'
import Container from 'react-bootstrap/Container'

import {UserInfoProvider, UserInfoContext, AdminOnly} from './common/userinfo';

import Home from './pane/home.js';

function App() {
	const userinfo = React.useContext(UserInfoContext);

	return <Router basename="/app">
				<Navbar bg="light" expand="sm">
					<Navbar.Brand>nffu</Navbar.Brand>
					<Navbar.Toggle aria-controls="responsive-navbar-nav" />
					<Navbar.Collapse id="responsive-navbar-nav">
						<Nav className="mr-auto">
							<LinkContainer to="/" exact>
								<Nav.Link>Home</Nav.Link>
							</LinkContainer>
							<AdminOnly>
								<LinkContainer to="/forms">
									<Nav.Link>Forms</Nav.Link>
								</LinkContainer>
								<LinkContainer to="/authcfg">
									<Nav.Link>Authentication Config</Nav.Link>
								</LinkContainer>
							</AdminOnly>
							<LinkContainer to="/lockbox">
								<Nav.Link>TDSB Credentials</Nav.Link>
							</LinkContainer>
						</Nav>
						<Navbar.Text>
							Logged in as <b>{userinfo.name}</b>
						</Navbar.Text>
						<Nav>
							<Nav.Link href="/logout">Logout</Nav.Link>
						</Nav>
				  </Navbar.Collapse>
				</Navbar>
				<Container className="mt-2">
					<Switch>
						<Route path="/" exact>
							<Home />
						</Route>
					</Switch>
				</Container>
			</Router>
}

const mount = document.getElementById("mount");
ReactDOM.render(<UserInfoProvider><App /></UserInfoProvider>, mount);
