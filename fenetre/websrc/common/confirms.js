import reactModal from '@prezly/react-promise-modal';
import React from 'react';

import {Button, Modal, Form} from 'react-bootstrap';
import {Formik} from 'formik';
import * as yup from 'yup';

function imageHighlight(src) {
	return reactModal(({show, onDismiss}) => (
		<Modal size="xl" centered show={show} onHide={onDismiss}>
			<Modal.Body>
				<img className="d-block img-fluid img-thumbnail" src={src} />
			</Modal.Body>
		</Modal>
	));
}

function confirmationDialog(body) {
	return reactModal(({show, onSubmit, onDismiss}) => (
		<Modal centered show={show} onHide={onDismiss}>
			<Modal.Body>
				{body}
			</Modal.Body>

			<Modal.Footer>
				<Button variant="secondary" onClick={onDismiss}>No</Button>
				<Button variant="primary" onClick={onSubmit}>Yes</Button>
			</Modal.Footer>
		</Modal>
	));
}

function passwordChangeDialog(body) {
	const schema = yup.object({
		password: yup.string().required().min(8),
		passwordConfirm: yup.string().test(
			'is-same',
			'passwords do not match',
			function(v) {
				return v === this.resolve(yup.ref('password'));
			}
		)
	});

	return reactModal(({show, onSubmit, onDismiss}) => {
		return <Modal backdrop="static" centered show={show} onHide={onDismiss}>
			<Modal.Header>
				<Modal.Title>
					{body}
				</Modal.Title>
			</Modal.Header>
			<Formik validationSchema={schema}
				onSubmit={(values) => {onSubmit(values.password);}}
				initialValues={{
					password: '', passwordConfirm: ''
				}}
			>
				{({
					handleSubmit,
					handleChange,
					values,
					errors,
				}) => (
				<Form noValidate onSubmit={handleSubmit}>
					<Modal.Body>
						<Form.Group>
							<Form.Control 
								name="password" 
								type="password" 
								placeholder="Enter a new password"
								onChange={handleChange}
								isInvalid={!!errors.password}
								value={values.password}
							/>
							<Form.Control.Feedback type="invalid">
								{errors.password}
							</Form.Control.Feedback>
						</Form.Group>

						<Form.Group>
							<Form.Control 
								name="passwordConfirm" 
								type="password" 
								placeholder="Confirm new password"
								onChange={handleChange}
								isInvalid={!!errors.passwordConfirm}
								value={values.passwordConfirm}
							/>
							<Form.Control.Feedback type="invalid">
								{errors.passwordConfirm}
							</Form.Control.Feedback>
						</Form.Group>
					</Modal.Body>

					<Modal.Footer>
						<Button variant="secondary" onClick={onDismiss}>Cancel</Button>
						<Button type="submit" variant="primary">OK</Button>
					</Modal.Footer>
				</Form>
			)}
			</Formik>
		</Modal>
	});
}

export {confirmationDialog, passwordChangeDialog, imageHighlight}
