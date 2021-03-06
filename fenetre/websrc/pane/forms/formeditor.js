import {highlight} from 'prismjs/components/prism-core';
import 'prismjs/themes/prism-okaidia.css';
import React from 'react';
import {Alert, Button, Col, Form, Row, Spinner} from 'react-bootstrap';
import {BsArrowLeft} from 'react-icons/bs';
import {Link, Redirect, useParams} from 'react-router-dom';
import Editor from 'react-simple-code-editor';
import "regenerator-runtime/runtime";
import * as yup from 'yup';
import {confirmationDialog, imageHighlight, textInputDialog} from '../../common/confirms';
import "../../css/code-input.scss";

const prismSimpleLanguage = {
	'string': {
		pattern: /(')(?:\\(?:\r\n|[\s\S])|(?!\1)[^\\\r\n])*\1/,
		greedy: true
	},
	'number': /[+-]?\d+/,
	'operator': /[<>]=?|[=!]=|\|\||&&|[+-/*%]/,
	'function': /\w+(?=\s*\()/,
	'keyword': /\$\s*\w+/
};

function SubFieldEditor(props) {
	return <div>
		<Form.Row>
			<Col md lg="4">
				<Form.Group>
					<Form.Label>Question index</Form.Label>
					<Form.Control type="number" value={props.field.index_on_page} onChange={(e) => props.onChangeIndex(e.target.value)} />
				</Form.Group>
			</Col>
			<Col md lg="8">
				<Form.Group>
					<Form.Label>Field label</Form.Label>
					<Form.Control type="text" value={props.field.expected_label_segment} onChange={(e) => props.onChangeSearch(e.target.value)} />
				</Form.Group>
			</Col>
		</Form.Row>
		<Form.Row>
			<Col md lg="10">
				<Form.Group>
					<Form.Label>Field type</Form.Label>
					<Form.Control as="select" custom value={props.field.kind} onChange={(e) => props.onChangeType(e.target.value)}>
						<option value="text">Text</option>
						<option value="long-text">Long answer</option>
						<option value="date">Date</option>
						<option value="multiple-choice">Multiple choice</option>
						<option value="checkbox">Checkbox</option>
						<option value="dropdown">Dropdown</option>
					</Form.Control>
				</Form.Group>
			</Col>
			<Col md lg="2" className="d-flex justify-content-center flex-column">
				<Form.Check onChange={(e) => props.onChangeCritical(e.target.checked)} checked={props.field.critical} label="Is critical?" custom id={props.field.index_on_page + "-swchk"} />
			</Col>
		</Form.Row>
		<Form.Row>
			<Form.Group as={Col}>
				<Form.Label>Value expression</Form.Label>
				<Editor padding={10} className="simple-eval-mono " value={props.field.target_value} onValueChange={(e) => props.onChangeValue(e)} highlight={code => highlight(code, prismSimpleLanguage)}/>
				<Form.Text className="text-muted">
					For more information on how these expressions work, see the documentation <a className="alert-link" href="https://github.com/tylertian123/nffu/blob/master/docs/fieldexpr.md" target="_blank">on GitHub here</a>
				</Form.Text>
			</Form.Group>
		</Form.Row>
		<div className="d-flex w-100 justify-content-end">
			<Button onClick={props.onRemove} variant="danger">Remove</Button>
		</div>
		<hr />
	</div>
}

function FormFieldEditor(props) {
	const [isDirty, setIsDirty] = React.useState(false);
	const [isSaving, setIsSaving] = React.useState(false);

	const [fields, dispatch] = React.useReducer((state, action) => {
		setIsDirty(true);
		const n = [...state];
		switch (action.type) {
			case 'add':
				return [
					...state,
					{
						index_on_page: -1,
						expected_label_segment: "",
						kind: "text",
						target_value: "''",
						critical: true
					}
				];
			case 'remove':
				return state.slice(0, action.index).concat(state.slice(action.index+1));
			case 'change_type':
				n[action.index].kind = action.value;
				break;
			case 'change_value':
				n[action.index].target_value = action.value;
				break;
			case 'change_search':
				n[action.index].expected_label_segment = action.value;
				break;
			case 'change_index':
				n[action.index].index_on_page = action.value;
				break;
			case 'change_critical':
				n[action.index].critical = action.value;
				break;
		}
		return n;
	}, props.fields);

	const save = async () => {
		setIsSaving(true);

		const resp = await fetch(`/api/v1/form/${props.idx}`, {
			method: "PATCH",
			headers: {"Content-Type": "application/json"},
			body: JSON.stringify({
				sub_fields: fields
			})
		});

		setIsSaving(false);

		if (!resp.ok) {
			alert((await resp.json()).error);
		}
		else {
			setIsDirty(false);
		}
	};

	return <div>
		{fields.map((x, idx) =>
		<SubFieldEditor field={x} key={idx}
			onChangeValue={v => dispatch({type: 'change_value', index: idx, value: v})}
			onChangeSearch={v => dispatch({type: 'change_search', index: idx, value: v})}
			onChangeType={v => dispatch({type: 'change_type', index: idx, value: v})}
			onChangeIndex={v => dispatch({type: 'change_index', index: idx, value: v})}
			onChangeCritical={v => dispatch({type: 'change_critical', index: idx, value: v})}
			onRemove={() => dispatch({type: 'remove', index: idx})}
		/>)}
		<div className="d-flex w-100 justify-content-end">
			<Button onClick={() => dispatch({type: 'add'})} variant="success" className="mr-1">Add</Button>
			<Button disabled={!isDirty || isSaving} onClick={save}>{isSaving ? <Spinner animation="border" size="sm" /> : 'Save'}</Button>
		</div>
	</div>
}

function FormEditor() {
	const { idx } = useParams();

	const [ form, setForm ] = React.useState(null);
	const [ error, setError ] = React.useState('');
	const [ redirecting, setRedirecting ] = React.useState(false);
	const [ processing, setProcessing ] = React.useState('');

	function sleep(ms) {
	  return new Promise(resolve => setTimeout(resolve, ms));
	}

	React.useEffect(() => {
		(async () => {
			const resp = await fetch("/api/v1/form/" + idx);
			const data = await resp.json();

			if (!resp.ok) {
				setError(data.error);
				return;
			}

			else {
				setForm(data.form);
			}
		})();
	}, [idx]);

	if (form === null) {
		if (error) {
			return <Alert variant="danger">failed: {error}</Alert>;
		}
		else {
			return <Alert className="d-flex align-items-center" variant="secondary"><Spinner className="mr-2" animation="border" /> loading...</Alert>;
		}
	}

	const changeName = async () => {
		const newName = await textInputDialog(<p>Enter a new name:</p>);
		if (newName) {
			setProcessing("Changing name...");
			const resp = await fetch(`/api/v1/form/${idx}`, {
				method: "PATCH",
				headers: {"Content-Type": "application/json"},
				body: JSON.stringify({
					name: newName
				})
			});
			setProcessing('');

			if (!resp.ok) {
				// todo show error
				alert((await resp.json()).error);
			}
			else {
				setForm({...form, name: newName});
			}
		}
	};

	const deleteMe = async () => {
		if (await confirmationDialog(<p>Are you sure you want to delete the form <code>{form.name}</code>? {!!form.used_by && <b>It is still used by <span class="text-info">{form.used_by}</span> courses</b>}</p>)) {
			setProcessing("deleting");

			const resp = await fetch(`/api/v1/form/${idx}`, {
				method: "DELETE",
			});

			if (!resp.ok) {
				// todo show error
				alert((await resp.json()).error);
				setProcessing('');
			}
			else {
				setRedirecting(true);
			}
		}
	}

	const updateThumbnail = async () => {
		const newUrl = await textInputDialog(<p>Enter URL to load new thumbnail from:</p>, yup.string().required().matches(/^(?:https?:\/\/)?docs.google.com\/forms(?:\/u\/\d+)?\/d\/e\/([A-Za-z0-9-_]+)\/viewform/, "url should be a google form url"));
		if (!newUrl) return;

		setProcessing("Updating thumbnail...");
		let tries = 0;
		while (tries < 10) {
			const resp = await fetch(`/api/v1/form/${idx}`, {
				method: "PUT",
				headers: {"Content-Type": "application/json"},
				body: JSON.stringify({
					initialize_from: newUrl
				})
			});
			const data = await resp.json();

			if (!resp.ok) {
				alert(data.error);
				setProcessing('');
				return;
			}
			else if (data.status == "pending") {
				setProcessing("Downloading thumbnail image...");
			}
			else {
				setForm({...form, representative_thumbnail: data.form.representative_thumbnail});
				setProcessing('');
				return;
			}

			await sleep(2800);
			++tries;
		}

		alert("timed out");
	};

	if (redirecting) return <Redirect to="/forms/form" />;

	return <div>
		<Link to="/forms/form"><span className="text-secondary"><BsArrowLeft /> Back</span></Link>
		{processing && <Alert className="d-flex align-items-center my-1" variant="secondary"><Spinner className="mr-2" animation="border" /> {processing}</Alert>}
		<Row>
			<Col sm>
				<h1>{form.name}</h1>
				<ul>
					<li>Used by <span className="text-info">{form.used_by}</span> courses</li>
					{form.is_default && <li><i>set as default</i></li>}
					{!!form.representative_thumbnail || <li><i>no thumbnail set</i></li>}
				</ul>
			</Col>
			<Col sm>
				{!!form.representative_thumbnail && <img onClick={() => imageHighlight(`/api/v1/form/${form.id}/thumb.png`)} className="d-block img-fluid img-thumbnail" src={`/api/v1/form/${form.id}/thumb.png`} />}
				<div className="d-flex w-100 justify-content-end mt-3">
					<Button onClick={changeName} className="mx-1">Change name</Button>
					<Button onClick={updateThumbnail} className="">{form.representative_thumbnail ? "Update thumbnail" : "Add thumbnail"}</Button>
					<Button onClick={deleteMe} variant="danger" className="mx-1">Delete</Button>
				</div>
			</Col>
		</Row>
		<hr />
		<h2>Fields</h2>
		<FormFieldEditor idx={form.id} fields={form.sub_fields} />
	</div>
}

export default FormEditor;
