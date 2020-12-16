import React from 'react';
import reactModal from '@prezly/react-promise-modal';

import {Row, Col, FormCheck, Form, Button, Alert, Spinner, ListGroup, Modal} from 'react-bootstrap';
import {ExtraUserInfoContext} from '../../common/userinfo';
import {Formik} from 'formik';
import * as yup from 'yup';
import {Link, Redirect, Switch, Route, useParams} from 'react-router-dom';
import useBackoffEffect from '../../common/pendprovider';

import {BsX, BsCheck, BsExclamationCircle, BsArrowRight, BsArrowLeft, BsArrowClockwise, BsPlus} from 'react-icons/bs';
import {imageHighlight} from '../../common/confirms';

import "regenerator-runtime/runtime";
import "../../css/code-input.scss";

import Editor from 'react-simple-code-editor';
import { highlight } from 'prismjs/components/prism-core';
import 'prismjs/themes/prism-okaidia.css';

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
			<Form.Group as={Col}>
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
		</Form.Row>
		<Form.Row>
			<Form.Group as={Col}>
				<Form.Label>Value expression</Form.Label>
				<Editor padding={10} className="simple-eval-mono " value={props.field.target_value} onValueChange={(e) => props.onChangeValue(e)} highlight={code => highlight(code, prismSimpleLanguage)}/>
			</Form.Group>
		</Form.Row>
		<div className="d-flex w-100 justify-content-end">
			<Button onClick={props.onRemove} variant="danger">Remove</Button>
		</div>
		<hr />
	</div>
}

function FormFieldEditor(props) {
	const [fields, dispatch] = React.useReducer((state, action) => {
		const n = [...state];
		switch (action.type) {
			case 'add':
				return [
					...state,
					{
						index_on_page: -1,
						expected_label_segment: "",
						kind: "text",
						target_value: "''"
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
		}
		return n;
	}, props.fields);

	return <div>
		{fields.map((x, idx) =>
		<SubFieldEditor field={x} key={idx}
			onChangeValue={v => dispatch({type: 'change_value', index: idx, value: v})}
			onChangeSearch={v => dispatch({type: 'change_search', index: idx, value: v})}
			onChangeType={v => dispatch({type: 'change_type', index: idx, value: v})}
			onChangeIndex={v => dispatch({type: 'change_index', index: idx, value: v})}
			onRemove={() => dispatch({type: 'remove', index: idx})}
		/>)}
		<div className="d-flex w-100 justify-content-end">
			<Button onClick={() => dispatch({type: 'add'})} variant="success" className="mr-1">Add</Button>
			<Button>Save</Button>
		</div>
	</div>
}

function FormEditor() {
	const { idx } = useParams();

	const [ form, setForm ] = React.useState(null);
	const [ error, setError ] = React.useState('');

	React.useEffect(() => {
		(async () => {
			const resp = await fetch("/api/v1/form/" + idx);
			const data = await resp.json();

			if (!resp.ok) {
				setError(data.error);
				return;
			}

			else {
				setForm(data);
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

	return <div>
		<Link to="/forms/form"><span className="text-secondary"><BsArrowLeft /> Back</span></Link>
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
				<div className="d-flex w-100 justify-content-end">
					<Button className="mt-3">{form.representative_thumbnail ? "Update thumbnail" : "Add thumbnail"}</Button>
				</div>
			</Col>
		</Row>
		<hr />
		<h2>Fields</h2>
		<FormFieldEditor fields={form.sub_fields} />
	</div>
}

export default FormEditor;
