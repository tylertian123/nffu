import "./css/boot.scss";

// Main logged-in page.
// Login page (and all non-logged-in flow) is handled in login.js

import ReactDOM from 'react-dom';
import React from 'react';

import {BrowserRouter as Router, Route} from 'react-router-dom'
import {LinkContainer} from 'react-router-bootstrap'
import Navbar from 'react-bootstrap/Navbar'
import Nav from 'react-bootstrap/Nav'
import Container from 'react-bootstrap/Container'

function App() {
	return <Router basename="/app">
				<Navbar>
					<Navbar.Brand>nffu</Navbar.Brand>
				</Navbar>
				<Container>
					<Route path="/" exact>
					</Route>
				</Container>
			</Router>
}

const mount = document.getElementById("mount");
ReactDOM.render(<App />, mount);
