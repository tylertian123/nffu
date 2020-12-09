import React from 'react';

import {Form, Spinner, ListGroup, Button} from 'react-bootstrap';
import {BsClipboard, BsPlus} from 'react-icons/bs';

import {confirmationDialog} from '../../common/confirms';

import "regenerator-runtime/runtime";

function FixedSignupProvider(props) {
	const [generated, setGenerated] = React.useState('');
	const [gone, setGone] = React.useState(false);

	const updateGenerated = () => {
		(async () => {
			const response = await fetch("/api/v1/signup_provider/" + props.id + "/generate");
			const data = await response.json();

			setGenerated(data.token);
		})();
	};

	const deleteMe = () => {
		(async () => {
			// Confirm the deletion
			if (!await confirmationDialog(<p>Are you sure you want to delete the signup provider <code>{props.name}</code></p>)) {
				return;
			}

			const response = await fetch("/api/v1/signup_provider/" + props.id, {
				"method": "DELETE"
			});

			if (response.ok)
				setGone(true);
		})();
	};

	const copy = () => {
		navigator.clipboard.writeText(generated);
	}

	if (gone) return <ListGroup.Item>deleted</ListGroup.Item>;

	return <ListGroup.Item>
		<span className="text-dark align-middle">{props.name}</span>{' '}
		<div className="float-right">
			{generated ? (<Button onClick={copy} size="sm" variant="outline-secondary"><BsClipboard /></Button>) : null}
			<span className="align-middle mx-1"> {generated}</span>{' '}
			<Button variant="outline-secondary" size="sm" onClick={updateGenerated}>Generate</Button>{' '}
			<Button variant="danger" size="sm" onClick={deleteMe}>Delete</Button>
		</div>
	</ListGroup.Item>;
}

function FreshSignupProvider(props) {
	return <ListGroup.Item>
		<span class="align-middle"><span className="text-dark">{props.name} &bull;{' '}</span>{props.hmac_secret}</span>
		<Button onClick={() => {navigator.clipboard.writeText(props.hmac_secret);}} variant="outline-secondary" size="sm" className="float-right"><BsClipboard /></Button>
	</ListGroup.Item>
}

function SignupProviders() {
	const [signupProviders, setSignupProviders] = React.useState(null);
	const [addedSignupProviders, setAddedSignupProviders] = React.useState([]);
	const [newName, setNewName] = React.useState('');

	React.useEffect(() => {
		// Load sign up providers
		(async () => {
			const response = await fetch("/api/v1/signup_provider");
			const data = await response.json();

			setSignupProviders(data.signup_providers);
		})();
	}, []);

	const addNew = () => {
		(async () => {
			const response = await fetch("/api/v1/signup_provider", {
				method: "POST", 
				headers: {"Content-Type": "application/json"},
				body: JSON.stringify({
					"name": newName
				})
			});
			const data = await response.json();

			if (!response.ok) {
				alert(data.error);
			}
			else {
				const new_data = [...addedSignupProviders, data];
				setAddedSignupProviders(new_data);
				setNewName("");
			}
		})();
	};

	return <>
		<ListGroup className="bg-light">
			{signupProviders === null ? (<ListGroup.Item>Loading... <Spinner size="sm" animation="border" /></ListGroup.Item>) : 
				signupProviders.map((provider) => (
					<FixedSignupProvider id={provider.id} name={provider.name} />))
			}
			{addedSignupProviders.map((provider) => (
				<FreshSignupProvider name={provider.name} id={provider.id} hmac_secret={provider.secret_key} />
			))}
		</ListGroup>
		<Form.Control value={newName} onChange={(e) => {setNewName(e.target.value);}} placeholder="Name for new provider" className="mt-2" type="text"/>
		<Button className="w-100 mt-1" variant="success" disabled={newName === ''} onClick={addNew}><BsPlus /></Button>
	</>
}

export default SignupProviders;
