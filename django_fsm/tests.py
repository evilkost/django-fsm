#-*- coding: utf-8 -*-
# pylint: disable=C0111, C0103, R0904

from django.test import TestCase
from django.db import models

from django_fsm.db.fields import FSMField, FSMKeyField, \
    transition, can_proceed, accessible_states

class BlogPost(models.Model):
    state = FSMField(default='new')

    @transition(source='new', target='published')
    def publish(self):
        pass

    @transition(source='published', target='hidden')
    def hide(self):
        pass

    @transition(source='new', target='removed')
    def remove(self):
        raise Exception('No rights to delete %s' % self)

    @transition(source=['published','hidden'], target='stolen')
    def steal(self):
        pass

    @transition(source='*', target='moderated')
    def moderate(self):
        pass


class FSMFieldTest(TestCase):
    def setUp(self):
        self.model = BlogPost()

    def test_initial_state_instatiated(self):
        self.assertEqual(self.model.state, 'new')

    def test_known_transition_should_succeed(self):
        self.assertTrue(can_proceed(self.model.publish))
        self.model.publish()
        self.assertEqual(self.model.state, 'published')

        self.assertTrue(can_proceed(self.model.hide))
        self.model.hide()
        self.assertEqual(self.model.state, 'hidden')

    def test_unknow_transition_fails(self):
        self.assertFalse(can_proceed(self.model.hide))
        self.assertRaises(NotImplementedError, self.model.hide)

    def test_state_non_changed_after_fail(self):
        self.assertTrue(can_proceed(self.model.remove))
        self.assertRaises(Exception, self.model.remove)
        self.assertEqual(self.model.state, 'new')

    def test_mutiple_source_support_path_1_works(self):
        self.model.publish()
        self.model.steal()
        self.assertEqual(self.model.state, 'stolen')

    def test_mutiple_source_support_path_2_works(self):
        self.model.publish()
        self.model.hide()
        self.model.steal()
        self.assertEqual(self.model.state, 'stolen')

    def test_star_shortcut_succeed(self):
        self.assertTrue(can_proceed(self.model.moderate))
        self.model.moderate()
        self.assertEqual(self.model.state, 'moderated')


class InvalidModel(models.Model):
    state = FSMField(default='new')
    action = FSMField(default='no')

    @transition(source='new', target='no')
    def validate(self):
        pass


class InvalidModelTest(TestCase):
    def test_two_fsmfields_in_one_model_not_allowed(self):
        model = InvalidModel()
        self.assertRaises(TypeError, model.validate)


class Document(models.Model):
    status = FSMField(default='new')

    @transition(source='new', target='published')
    def publish(self):
        pass


class DocumentTest(TestCase):
    def test_any_state_field_name_allowed(self):
        model = Document()
        model.publish()
        self.assertEqual(model.status, 'published')


class BlogPostStatus(models.Model):
    name = models.CharField(max_length=3, unique=True)
    objects = models.Manager()

    @transition(source='new', target='published')
    def publish(self):
        pass


class BlogPostWithFKState(models.Model):
    status = FSMKeyField(BlogPostStatus, default='new')

    @transition(source='new', target='published')
    def publish(self):
        pass
 
    @transition(source='published', target='hidden', save=True)
    def hide(self):
        pass


class BlogPostWithFKStateTest(TestCase):
    def setUp(self):
        self.model = BlogPost()
        BlogPostStatus.objects.create(name="new")
        BlogPostStatus.objects.create(name="published")
        BlogPostStatus.objects.create(name="hidden")

    def test_known_transition_should_succeed(self):
        self.model.publish()
        self.assertEqual(self.model.state, 'published')

        self.model.hide()
        self.assertEqual(self.model.state, 'hidden')

    def test_unknow_transition_fails(self):
        self.assertRaises(NotImplementedError, self.model.hide)

def condition_func(instance, *args, **kwargs):
    return True

def condition_func2(instance):
    return True

class BlogPostWithConditions(models.Model):
    state = FSMField(default='new')
    accessible = accessible_states

    def model_condition(self, *args, **kwargs):
        return True

    def unmet_condition(self, *args, **kwargs):
        return False

    def variable_condition(self, user, moderator='bar'):
        if user != moderator:
            return False
        return True

    @transition(source='new', target='published', conditions=[condition_func, model_condition])
    def publish(self):
        pass

    @transition(source='published', target='destroyed', conditions=[condition_func, unmet_condition])
    def destroy(self):
        pass

    @transition(source='published', target='approved', conditions=[condition_func, variable_condition])
    def approve(self, *args, **kwargs):
        pass

    @transition(source='published', target='holy', conditions=[variable_condition])
    def bless(self, *args, **kwargs):
        pass

    @transition(source=['published', 'new'], target='spam', conditions=[condition_func2,])
    def mark_spam(self, *args, **kwargs):
        pass

class ConditionalTest(TestCase):
    def setUp(self):
        self.model = BlogPostWithConditions()

    def test_initial_staet(self):
        self.assertEqual(self.model.state, 'new')

    def test_known_transition_should_succeed(self):
        self.assertTrue(can_proceed(self.model.publish))
        self.model.publish()
        self.assertEqual(self.model.state, 'published')

    def test_unmet_condition(self):
        self.model.publish()
        self.assertEqual(self.model.state, 'published')
        self.assertFalse(can_proceed(self.model.destroy))
        self.assertFalse(self.model.destroy())

    def test_variable_condition(self):
        self.model.publish()
        self.assertEqual(self.model.state, 'published')
        self.assertFalse(can_proceed(self.model.approve, 'foo'))
        self.assertTrue(can_proceed(self.model.approve, 'bar'))
        self.assertFalse(self.model.approve('foo'))
        self.model.approve('bar')
        self.assertEqual(self.model.state, 'approved')

    def test_variable_condition2(self):
        self.model.publish()
        self.assertEqual(self.model.state, 'published')
        self.assertFalse(can_proceed(self.model.approve, 'anonymous', moderator='root'))
        self.assertTrue(can_proceed(self.model.approve, 'root', moderator='root'))
        self.assertFalse(self.model.approve('anonymous', moderator='root'))
        self.model.approve('root', moderator='root')
        self.assertEqual(self.model.state, 'approved')

    def test_func_without_args_kwargs(self):
        self.model.publish()
        self.assertEqual(self.model.state, 'published')
        self.assertTrue(can_proceed(self.model.mark_spam))
        self.model.mark_spam()
        self.assertEqual(self.model.state, 'spam')

    def test_accessible_states(self):
        self.assertEqual(
            sorted(map(lambda (f,s): (f.func_name, s), accessible_states(self.model))),
            sorted([('publish', 'published'), ('mark_spam', 'spam')])
        )
        self.model.publish()
        self.assertEqual(
            sorted(map(lambda (f,s): (f.func_name, s), accessible_states(self.model))),
            sorted([('mark_spam', 'spam')])
        )
        self.assertEqual(
            sorted(map(lambda (f,s): (f.func_name, s), accessible_states(self.model, 'bar'))),
            sorted([('approve', 'approved'), ('bless', 'holy')])
        )
