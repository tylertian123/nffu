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
import NFFULogo from './logo.svg';

import Home from './pane/home.js';
import AuthCfg from './pane/authcfg.js';
import Lockbox from './pane/lockbox.js';
import Forms from './pane/forms.js';

function App() {
	const userinfo = React.useContext(UserInfoContext);

	return <Router basename="/app">
		<Navbar bg="light" expand="sm">
			<Navbar.Brand>
				<img
					alt="nffu logo"
					src={NFFULogo}
					width="32"
					height="32"
					className="d-inline-block align-middle"
				/>{' '}nffu</Navbar.Brand>
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
						<Nav.Link>Attendance Setup</Nav.Link>
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
		<Container className="my-2">
			<Switch>
				<Route path="/" exact>
					<Home />
				</Route>
				<Route path="/authcfg">
					<AuthCfg />
				</Route>
				<Route path="/lockbox">
					<Lockbox />
				</Route>
				<Route path="/forms">
					<Forms />
				</Route>
			</Switch>
		</Container>
	</Router>
}

const mount = document.getElementById("mount");
ReactDOM.render(<UserInfoProvider><App /></UserInfoProvider>, mount);
